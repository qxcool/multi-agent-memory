from __future__ import annotations

import json
import os
import re
import shutil
import socket
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence

from .companions import probe_companions
from .assembly import AssemblyMixin, search_results_as_dict
from .index import IndexMixin
from .lifecycle import LifecycleMixin
from .errors import MemoryHubError
from .maps import (
    LOCATE_HIT_HINT,
    LOCATE_MISS_HINT,
    MapsMixin,
    _normalize_path_fingerprints,
    _parse_map_fields,
    _path_fingerprints_for,
)
from .util import (
    atomic_write as _atomic_write,
    choice as _choice,
    content_fingerprint as _content_fingerprint,
    frontmatter as _frontmatter,
    lock_owner_gone as _lock_owner_gone,
    normalize_memory_key as _normalize_memory_key,
    now as _now,
    one_line as _one_line,
    safe_segment as _safe_segment,
    slug as _slug,
    split_frontmatter as _split_frontmatter,
    tokenize_query as _tokenize_query,
)


from .constants import (
    ACTIVE_MEMORY_COLLECTIONS,
    COLLECTIONS,
    CONFIDENCE_LEVELS,
    CORE_FILE_TEMPLATES,
    CORE_MEMORY_FILES,
    FEEDBACK_SIGNALS,
    HUB_DIRNAME,
    HUB_FORMAT_VERSION,
    INDEXED_COLLECTIONS,
    LIST_COLLECTIONS,
    MEMORY_TYPES,
    PROMOTE_TARGETS,
    RELATION_TYPES,
    STATUS_FIELDS,
    VERSION_FILENAME,
)

def resolve_hub(explicit: str | Path | None = None, *, start: Path | None = None) -> Path:
    """解析记忆库路径：显式 --hub → 向上查找 .ai-memory-hub → MEMORY_HUB_ROOT → 默认新建路径。"""
    start = (start or Path.cwd()).resolve()
    if explicit is not None:
        path = Path(explicit).expanduser()
        if path.is_absolute():
            return path.resolve()
        normalized = path.as_posix().removeprefix("./")
        if normalized != HUB_DIRNAME:
            return (start / path).resolve()
    current = start
    while True:
        candidate = current / HUB_DIRNAME
        if candidate.is_dir():
            return candidate.resolve()
        if current.parent == current:
            break
        current = current.parent
    env_hub = os.environ.get("MEMORY_HUB_ROOT", "").strip()
    if env_hub:
        return Path(env_hub).expanduser().resolve()
    return (start / HUB_DIRNAME).resolve()






class HubLock:
    """跨进程文件锁 + 同进程线程锁，避免同 PID 多线程争抢锁文件。"""

    _thread_locks_guard = threading.Lock()
    _thread_locks: dict[str, threading.Lock] = {}

    def __init__(self, root: Path, timeout: float = 60.0, stale_after: float = 120.0):
        self.path = root / ".memory-hub.lock"
        self.timeout = timeout
        self.stale_after = stale_after
        self.acquired = False
        self._thread_lock: threading.Lock | None = None
        self._thread_acquired = False

    @classmethod
    def _thread_lock_for(cls, path: Path) -> threading.Lock:
        key = str(path)
        with cls._thread_locks_guard:
            lock = cls._thread_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                cls._thread_locks[key] = lock
            return lock

    def _try_reclaim(self) -> bool:
        try:
            raw = self.path.read_text(encoding="utf-8")
            payload = json.loads(raw) if raw.strip().startswith("{") else {}
        except (OSError, json.JSONDecodeError):
            payload = {}
        age = time.time() - self.path.stat().st_mtime
        if _lock_owner_gone(payload) or age > self.stale_after:
            try:
                self.path.unlink()
                return True
            except FileNotFoundError:
                return True
            except OSError:
                return False
        return False

    def __enter__(self) -> "HubLock":
        deadline = time.monotonic() + self.timeout
        self._thread_lock = self._thread_lock_for(self.path)
        if not self._thread_lock.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise MemoryHubError(f"等待记忆库写锁超时：{self.path}")
        self._thread_acquired = True
        payload = json.dumps(
            {"pid": os.getpid(), "host": socket.gethostname(), "created": time.time()},
            ensure_ascii=False,
        )
        try:
            while True:
                try:
                    descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                        stream.write(payload)
                    self.acquired = True
                    return self
                except FileExistsError:
                    try:
                        if self._try_reclaim():
                            continue
                    except FileNotFoundError:
                        continue
                    if time.monotonic() >= deadline:
                        raise MemoryHubError(f"等待记忆库写锁超时：{self.path}")
                    time.sleep(0.05)
        except Exception:
            if self._thread_acquired and self._thread_lock is not None:
                self._thread_lock.release()
                self._thread_acquired = False
            raise

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        try:
            if self.acquired:
                for _ in range(5):
                    try:
                        self.path.unlink()
                        break
                    except FileNotFoundError:
                        break
                    except OSError:
                        time.sleep(0.05)
        finally:
            if self._thread_acquired and self._thread_lock is not None:
                self._thread_lock.release()
                self._thread_acquired = False


class MemoryHub(MapsMixin, LifecycleMixin, AssemblyMixin, IndexMixin):
    """以 Markdown 文件为存储介质的本地共享记忆库。"""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self._search_docs_cache: tuple[dict[str, object], dict[str, int]] | None = None

    def _ensure_initialized(self) -> None:
        if not self.root.is_dir() or not (self.root / "memory").is_dir():
            raise MemoryHubError(f"尚未初始化记忆库：{self.root}")

    @contextmanager
    def _write_lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        with HubLock(self.root):
            yield

    def init(self, *, track: bool = False) -> dict[str, object]:
        created: list[str] = []
        with self._write_lock():
            for name in COLLECTIONS:
                path = self.root / name
                if not path.exists():
                    path.mkdir(parents=True)
                    created.append(name + "/")
            (self.root / "archive" / "forgotten").mkdir(parents=True, exist_ok=True)
            for relative, content in CORE_FILE_TEMPLATES.items():
                path = self.root / relative
                if not path.exists():
                    _atomic_write(path, content)
                    created.append(relative)
            ignore = self.root / ".gitignore"
            if not track and not ignore.exists():
                _atomic_write(ignore, "*\n!.gitignore\n")
                created.append(".gitignore")
            self._write_version_unlocked(HUB_FORMAT_VERSION)
            created.append(VERSION_FILENAME)
            self._reindex_unlocked()
        return {
            "hub": str(self.root),
            "created": created,
            "tracked": track,
            "format_version": HUB_FORMAT_VERSION,
        }

    def format_version(self) -> str:
        path = self.root / VERSION_FILENAME
        if not path.is_file():
            return "0.0.0"
        try:
            value = path.read_text(encoding="utf-8").strip().splitlines()[0].strip()
        except (OSError, IndexError):
            return "0.0.0"
        return value or "0.0.0"

    def _write_version_unlocked(self, version: str) -> None:
        _atomic_write(self.root / VERSION_FILENAME, f"{version}\n")

    def migrate(
        self,
        *,
        dry_run: bool = False,
        backfill_hash: bool = False,
        backfill_map_fingerprints: bool = False,
    ) -> dict[str, object]:
        """将旧记忆库结构升级到当前格式（幂等）。"""
        if not self.root.exists():
            raise MemoryHubError(f"记忆库目录不存在：{self.root}")
        current = self.format_version()
        planned: list[str] = []
        created: list[str] = []
        updated: list[str] = []
        hashed: list[str] = []

        for name in COLLECTIONS:
            path = self.root / name
            if not path.is_dir():
                planned.append(f"create-dir:{name}/")
        forgotten = self.root / "archive" / "forgotten"
        if not forgotten.is_dir():
            planned.append("create-dir:archive/forgotten/")
        for relative in CORE_FILE_TEMPLATES:
            if not (self.root / relative).exists():
                planned.append(f"create-file:{relative}")
        ignore = self.root / ".gitignore"
        if not ignore.exists():
            planned.append("create-file:.gitignore")
        if current != HUB_FORMAT_VERSION:
            planned.append(f"set-version:{current}->{HUB_FORMAT_VERSION}")
        planned.append("reindex")

        hash_candidates: list[Path] = []
        if backfill_hash:
            for path in self.root.rglob("*.md"):
                if path.name == "INDEX.md":
                    continue
                relative = path.relative_to(self.root)
                if relative.as_posix() in CORE_FILE_TEMPLATES:
                    continue
                if relative.parts and relative.parts[0] == "sessions":
                    continue
                try:
                    metadata, body = _split_frontmatter(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError):
                    continue
                if not metadata:
                    continue
                existing = metadata.get("content_hash")
                if isinstance(existing, str) and existing:
                    continue
                hash_candidates.append(path)
                planned.append(f"backfill-hash:{relative.as_posix()}")

        fingerprint_candidates: list[tuple[Path, dict[str, object], str, dict[str, str]]] = []
        if backfill_map_fingerprints:
            project_root = self.root.parent
            for collection in ("wiki", "experiences", "inbox"):
                base = self.root / collection
                if not base.is_dir():
                    continue
                for path in base.glob("*.md"):
                    if path.name == "INDEX.md":
                        continue
                    try:
                        metadata, body = _split_frontmatter(path.read_text(encoding="utf-8"))
                    except (OSError, UnicodeDecodeError):
                        continue
                    key = metadata.get("key") if isinstance(metadata.get("key"), str) else ""
                    tags = metadata.get("tags", [])
                    tag_list = [str(item).casefold() for item in tags] if isinstance(tags, list) else []
                    is_map = key.casefold().startswith("feature:") or "map" in tag_list
                    if not is_map:
                        continue
                    meta_paths = metadata.get("paths")
                    path_list = [str(item) for item in meta_paths] if isinstance(meta_paths, list) else []
                    if not path_list:
                        parsed = _parse_map_fields(body)
                        path_list = [str(item) for item in parsed.get("paths") or []]
                    if not path_list:
                        continue
                    new_fps = _path_fingerprints_for(project_root, path_list)
                    old_fps = _normalize_path_fingerprints(metadata.get("path_fingerprints"))
                    if not new_fps or new_fps == old_fps:
                        continue
                    fingerprint_candidates.append((path, metadata, body, new_fps))
                    planned.append(f"backfill-map-fp:{path.relative_to(self.root).as_posix()}")

        if dry_run:
            return {
                "hub": str(self.root),
                "dry_run": True,
                "from_version": current,
                "to_version": HUB_FORMAT_VERSION,
                "planned": planned,
                "created": [],
                "updated": [],
                "hashed": [],
                "map_fingerprints": [],
            }

        with self._write_lock():
            for name in COLLECTIONS:
                path = self.root / name
                if not path.exists():
                    path.mkdir(parents=True)
                    created.append(name + "/")
            forgotten.mkdir(parents=True, exist_ok=True)
            if "create-dir:archive/forgotten/" in planned and "archive/forgotten/" not in created:
                created.append("archive/forgotten/")
            for relative, content in CORE_FILE_TEMPLATES.items():
                path = self.root / relative
                if not path.exists():
                    _atomic_write(path, content)
                    created.append(relative)
            if not ignore.exists():
                _atomic_write(ignore, "*\n!.gitignore\n")
                created.append(".gitignore")
            for path in hash_candidates:
                try:
                    metadata, body = _split_frontmatter(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError):
                    continue
                metadata["content_hash"] = _content_fingerprint(body)
                _atomic_write(path, _frontmatter(metadata) + body.lstrip("\n"))
                hashed.append(path.relative_to(self.root).as_posix())
            fingerprinted: list[str] = []
            for path, metadata, body, new_fps in fingerprint_candidates:
                metadata["path_fingerprints"] = new_fps
                if "authority" not in metadata:
                    metadata["authority"] = ""
                if "stale_reason" not in metadata:
                    metadata["stale_reason"] = ""
                _atomic_write(path, _frontmatter(metadata) + body.lstrip("\n"))
                fingerprinted.append(path.relative_to(self.root).as_posix())
            self._write_version_unlocked(HUB_FORMAT_VERSION)
            updated.append(VERSION_FILENAME)
            counts = self._reindex_unlocked()
            updated.append("INDEX.md")

        return {
            "hub": str(self.root),
            "dry_run": False,
            "from_version": current,
            "to_version": HUB_FORMAT_VERSION,
            "planned": planned,
            "created": created,
            "updated": updated,
            "hashed": hashed,
            "map_fingerprints": fingerprinted,
            "index": counts,
        }

    def get_status(self, *, task: str, agent: str) -> dict[str, object]:
        self._ensure_initialized()
        task = _safe_segment(task, "任务名")
        agent = _safe_segment(agent, "代理名")
        path = self.root / "sessions" / task / f"{agent}.md"
        if not path.is_file():
            raise MemoryHubError(f"任务状态不存在：{task}/{agent}")
        parsed = self._parse_status(path)
        return {"task": task, "agent": agent, "path": str(path), **parsed}

    def update_status(
        self,
        *,
        task: str,
        agent: str,
        objective: str | None = None,
        state: str | None = None,
        completed: Sequence[str] = (),
        next_step: str | None = None,
        blocker: str | None = None,
        steps: str | None = None,
        query: str | None = None,
        append_completed: bool = False,
    ) -> dict[str, object]:
        self._ensure_initialized()
        task = _safe_segment(task, "任务名")
        agent = _safe_segment(agent, "代理名")
        path = self.root / "sessions" / task / f"{agent}.md"
        with self._write_lock():
            previous = self._parse_status(path) if path.exists() else {}
            previous_completed = list(previous.get("completed", []) or [])
            if completed:
                incoming = [_one_line(str(item)) for item in completed if str(item).strip()]
                if append_completed:
                    merged = list(previous_completed)
                    for item in incoming:
                        if item not in merged:
                            merged.append(item)
                    completed_values: list[str] = merged
                else:
                    completed_values = incoming
            else:
                completed_values = previous_completed
            pinned_query = _one_line(query) if query is not None else _one_line(str(previous.get("query", "")))
            values: dict[str, object] = {
                "objective": objective if objective is not None else previous.get("objective", ""),
                "steps": steps if steps is not None else previous.get("steps", ""),
                "completed": completed_values,
                "state": state if state is not None else previous.get("state", "in-progress"),
                "blocker": blocker if blocker is not None else previous.get("blocker", "无"),
                "next_step": next_step if next_step is not None else previous.get("next_step", ""),
                "query": pinned_query,
            }
            title = _one_line(str(values["objective"])) or task
            completed_text = "；".join(_one_line(str(item)) for item in values["completed"] if str(item).strip())
            body = (
                f"# {title}\n\n"
                f"- 目标：{_one_line(str(values['objective']))}\n"
                f"- 步骤：{_one_line(str(values['steps']))}\n"
                f"- 已完成：{completed_text}\n"
                f"- 当前状态：{_one_line(str(values['state']))}\n"
                f"- 阻塞：{_one_line(str(values['blocker']))}\n"
                f"- 下一步：{_one_line(str(values['next_step']))}\n"
                f"- 检索词：{_one_line(str(values['query']))}\n"
            )
            _atomic_write(path, body)
            self._touch_index_unlocked(sessions=True)
        return {"task": task, "agent": agent, "path": str(path), **values}

    def _parse_status(self, path: Path) -> dict[str, object]:
        parsed: dict[str, object] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^-\s*([^：:]+)[：:]\s*(.*)$", line)
            if not match:
                continue
            key = STATUS_FIELDS.get(match.group(1).strip())
            if not key:
                continue
            value = match.group(2).strip()
            parsed[key] = [item for item in value.split("；") if item] if key == "completed" else value
        return parsed

    def _resolve_inbox_source(self, *, memory_id: str | None = None, path: str | None = None) -> Path:
        if bool(memory_id) == bool(path):
            raise MemoryHubError("晋升时必须且只能指定 --id 或 --path 之一")
        if path:
            relative = Path(path.replace("\\", "/"))
            if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] != ("inbox",):
                raise MemoryHubError("晋升路径必须是相对 inbox/ 下的文件")
            source = (self.root / relative).resolve()
            try:
                source.relative_to(self.root / "inbox")
            except ValueError as error:
                raise MemoryHubError("晋升路径必须位于 inbox/") from error
            if not source.is_file() or source.name == "INDEX.md":
                raise MemoryHubError(f"inbox 文件不存在：{relative.as_posix()}")
            return source
        assert memory_id is not None
        memory_id = memory_id.strip()
        if not memory_id:
            raise MemoryHubError("记忆 ID 不能为空")
        for candidate in (self.root / "inbox").glob("*.md"):
            if candidate.name == "INDEX.md":
                continue
            try:
                metadata, _ = _split_frontmatter(candidate.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
            if metadata.get("id") == memory_id:
                return candidate
        raise MemoryHubError(f"inbox 中未找到记忆：{memory_id}")

    def promote(
        self,
        *,
        to: str,
        memory_id: str | None = None,
        path: str | None = None,
    ) -> dict[str, object]:
        self._ensure_initialized()
        target = _choice(to, PROMOTE_TARGETS, "晋升目标")
        source = self._resolve_inbox_source(memory_id=memory_id, path=path)
        if source.name.casefold() in {"core.md", "user.md", "agents.md"}:
            raise MemoryHubError("不能晋升为 CORE/USER/AGENTS 核心文件名")
        destination_dir = self.root / target
        destination = destination_dir / source.name
        try:
            metadata, _ = _split_frontmatter(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as error:
            raise MemoryHubError(f"无法读取待晋升文件：{error}") from error
        resolved_id = metadata.get("id") if isinstance(metadata.get("id"), str) else memory_id
        with self._write_lock():
            if destination.exists():
                raise MemoryHubError(f"目标已存在：{target}/{source.name}")
            destination_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            self._touch_index_unlocked(collections=("inbox", target))
        return {
            "id": resolved_id,
            "from": f"inbox/{source.name}",
            "to": f"{target}/{source.name}",
            "collection": target,
        }

    def _path_from_index_relative(self, relative: str) -> Path | None:
        candidate = Path(relative.replace("\\", "/"))
        if candidate.is_absolute() or ".." in candidate.parts:
            return None
        path = (self.root / candidate).resolve()
        try:
            path.relative_to(self.root)
        except ValueError:
            return None
        return path if path.is_file() else None

    def _find_duplicate_by_fingerprint(self, fingerprint: str) -> Path | None:
        docs = self._search_docs()
        for relative, doc in docs.items():
            if not isinstance(doc, dict):
                continue
            collection = str(doc.get("collection") or "")
            if collection not in ACTIVE_MEMORY_COLLECTIONS:
                continue
            if str(doc.get("content_hash") or "") == fingerprint:
                found = self._path_from_index_relative(str(relative))
                if found is not None:
                    return found
            # 旧记录无 content_hash：只补读这些条目，不再全库 rglob
            if doc.get("content_hash"):
                continue
            path = self._path_from_index_relative(str(relative))
            if path is None or path.name in CORE_MEMORY_FILES:
                continue
            try:
                _, body = _split_frontmatter(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
            if _content_fingerprint(body) == fingerprint:
                return path
        return None

    def _find_by_key(self, key: str) -> Path | None:
        """按 key 找活跃记忆；忽略 archive/forgotten，避免 forget 后被原地复活。"""
        key_cf = key.casefold()
        for relative, doc in self._search_docs().items():
            if not isinstance(doc, dict):
                continue
            collection = str(doc.get("collection") or "")
            if collection not in ACTIVE_MEMORY_COLLECTIONS:
                continue
            existing = doc.get("key")
            if isinstance(existing, str) and existing.casefold() == key_cf:
                found = self._path_from_index_relative(str(relative))
                if found is not None:
                    return found
        return None

    def _remember_payload(
        self,
        path: Path,
        metadata: dict[str, object],
        *,
        deduped: bool = False,
        updated: bool = False,
    ) -> dict[str, object]:
        tags = metadata.get("tags", [])
        clean_tags = [str(item) for item in tags] if isinstance(tags, list) else []
        return {
            "path": str(path),
            "agent": str(metadata.get("source_agent", "")),
            "tags": clean_tags,
            "deduped": deduped,
            "updated": updated,
            **metadata,
        }

    def _write_remember_file(
        self,
        path: Path,
        *,
        metadata: dict[str, object],
        agent: str,
        text: str,
        clean_tags: Sequence[str],
        stamp: str,
    ) -> None:
        body = _frontmatter(metadata) + (
            f"# {_one_line(text)[:80]}\n\n"
            f"- Agent: {agent}\n"
            f"- Created: {stamp}\n"
            f"- Tags: {', '.join(clean_tags)}\n\n"
            f"{text.rstrip()}\n"
        )
        _atomic_write(path, body)

    def remember(
        self,
        *,
        agent: str,
        text: str,
        tags: Sequence[str] = (),
        memory_type: str = "note",
        source_task: str | None = None,
        confidence: str = "unspecified",
        links: Sequence[tuple[str, str]] = (),
        key: str | None = None,
    ) -> dict[str, object]:
        self._ensure_initialized()
        agent = _safe_segment(agent, "代理名")
        text = text.strip()
        if not text:
            raise MemoryHubError("记忆内容不能为空")
        memory_type = _choice(memory_type, MEMORY_TYPES, "记忆类型")
        confidence = _choice(confidence, CONFIDENCE_LEVELS, "置信度")
        clean_source_task = _safe_segment(source_task, "来源任务") if source_task else ""
        clean_key = _normalize_memory_key(key) if key else ""
        clean_links: list[dict[str, str]] = []
        for relation, target in links:
            clean_relation = _choice(relation, RELATION_TYPES, "关系类型")
            clean_target = _one_line(target)
            if not clean_target:
                raise MemoryHubError("关系目标不能为空")
            clean_links.append({"relation": clean_relation, "target": clean_target})
        fingerprint = _content_fingerprint(text)
        now = _now()
        stamp = now.isoformat(timespec="seconds")
        clean_tags = [_one_line(tag) for tag in tags if tag.strip()]

        with self._write_lock():
            if clean_key:
                existing_path = self._find_by_key(clean_key)
                if existing_path is not None:
                    old_meta, _ = _split_frontmatter(existing_path.read_text(encoding="utf-8"))
                    old_hash = old_meta.get("content_hash")
                    if isinstance(old_hash, str) and old_hash == fingerprint:
                        return self._remember_payload(existing_path, old_meta, deduped=True)
                    memory_id = str(old_meta.get("id") or f"mem-{uuid.uuid4().hex}")
                    created_at = str(old_meta.get("created_at") or stamp)
                    metadata = {
                        "id": memory_id,
                        "key": clean_key,
                        "type": memory_type,
                        "source_task": clean_source_task,
                        "source_agent": agent,
                        "created_at": created_at,
                        "updated_at": stamp,
                        "confidence": confidence,
                        "tags": clean_tags,
                        "links": clean_links,
                        "content_hash": fingerprint,
                    }
                    self._write_remember_file(
                        existing_path,
                        metadata=metadata,
                        agent=agent,
                        text=text,
                        clean_tags=clean_tags,
                        stamp=created_at,
                    )
                    collection = existing_path.relative_to(self.root).parts[0]
                    self._touch_index_unlocked(
                        collections=(collection,) if collection in INDEXED_COLLECTIONS else ()
                    )
                    return self._remember_payload(existing_path, metadata, updated=True)

            duplicate = self._find_duplicate_by_fingerprint(fingerprint)
            if duplicate is not None:
                metadata, _ = _split_frontmatter(duplicate.read_text(encoding="utf-8"))
                return self._remember_payload(duplicate, metadata, deduped=True)

            memory_id = f"mem-{uuid.uuid4().hex}"
            stem = f"{now:%Y%m%d-%H%M%S}-{_slug(agent)}-{_slug(text[:32])}"
            metadata = {
                "id": memory_id,
                "type": memory_type,
                "source_task": clean_source_task,
                "source_agent": agent,
                "created_at": stamp,
                "confidence": confidence,
                "tags": clean_tags,
                "links": clean_links,
                "content_hash": fingerprint,
            }
            if clean_key:
                metadata["key"] = clean_key
            path = self.root / "inbox" / f"{stem}.md"
            counter = 1
            while path.exists():
                path = self.root / "inbox" / f"{stem}-{counter}.md"
                counter += 1
            self._write_remember_file(
                path,
                metadata=metadata,
                agent=agent,
                text=text,
                clean_tags=clean_tags,
                stamp=stamp,
            )
            self._touch_index_unlocked(collections=("inbox",))
        return self._remember_payload(path, metadata)

    def _feedback_unlocked(
        self,
        *,
        signal: str,
        memory_id: str | None = None,
        path: str | None = None,
        reason: str | None = None,
    ) -> dict[str, object]:
        """feedback 写盘（调用方已持写锁）；不触碰索引。"""
        signal = _choice(signal, FEEDBACK_SIGNALS, "反馈信号")
        source = self._resolve_memory_file(memory_id=memory_id, path=path)
        relative = source.relative_to(self.root)
        if relative.parts[:2] == ("archive", "forgotten"):
            raise MemoryHubError("已遗忘记忆不能反馈")
        if relative.parts[0] == "sessions":
            raise MemoryHubError("任务状态请用 status，不能 feedback")
        if relative.as_posix() in {f"memory/{name}" for name in CORE_MEMORY_FILES}:
            raise MemoryHubError("不能对核心记忆文件直接 feedback")
        try:
            metadata, body = _split_frontmatter(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as error:
            raise MemoryHubError(f"无法读取记忆：{error}") from error
        if not metadata:
            metadata = {
                "id": f"mem-{uuid.uuid4().hex}",
                "type": "legacy",
                "created_at": _now().isoformat(timespec="seconds"),
                "confidence": "unspecified",
                "tags": [],
                "links": [],
            }
        useful = int(metadata.get("feedback_useful") or 0)
        stale = int(metadata.get("feedback_stale") or 0)
        wrong = int(metadata.get("feedback_wrong") or 0)
        tags = metadata.get("tags", [])
        tag_list = [str(item) for item in tags] if isinstance(tags, list) else []
        confidence = str(metadata.get("confidence") or "unspecified").casefold()
        if confidence not in CONFIDENCE_LEVELS:
            confidence = "unspecified"

        clean_reason = _one_line(reason) if reason else ""
        if signal == "useful":
            useful += 1
            if useful >= 2 and confidence in {"unspecified", "tentative", "inferred"}:
                confidence = "confirmed"
            tag_list = [tag for tag in tag_list if tag.casefold() not in {"stale", "disputed"}]
            metadata["stale_reason"] = ""
        elif signal == "stale":
            stale += 1
            if "stale" not in {tag.casefold() for tag in tag_list}:
                tag_list.append("stale")
            if confidence == "confirmed":
                confidence = "tentative"
            if clean_reason:
                metadata["stale_reason"] = clean_reason
        else:
            wrong += 1
            if "disputed" not in {tag.casefold() for tag in tag_list}:
                tag_list.append("disputed")
            confidence = "inferred"

        metadata["feedback_useful"] = useful
        metadata["feedback_stale"] = stale
        metadata["feedback_wrong"] = wrong
        metadata["confidence"] = confidence
        metadata["tags"] = tag_list
        metadata["updated_at"] = _now().isoformat(timespec="seconds")
        if "content_hash" not in metadata:
            metadata["content_hash"] = _content_fingerprint(body)
        _atomic_write(source, _frontmatter(metadata) + body.lstrip("\n"))
        return {
            "id": metadata.get("id"),
            "path": relative.as_posix(),
            "signal": signal,
            "confidence": confidence,
            "feedback_useful": useful,
            "feedback_stale": stale,
            "feedback_wrong": wrong,
            "tags": tag_list,
            "stale_reason": metadata.get("stale_reason") or None,
            "collection": relative.parts[0],
        }

    def feedback(
        self,
        *,
        signal: str,
        memory_id: str | None = None,
        path: str | None = None,
        reason: str | None = None,
    ) -> dict[str, object]:
        """对记忆投票：useful 巩固，stale/wrong 降权，驱动自我进化。"""
        self._ensure_initialized()
        with self._write_lock():
            result = self._feedback_unlocked(
                signal=signal, memory_id=memory_id, path=path, reason=reason
            )
            collection = str(result.get("collection") or "")
            self._touch_index_unlocked(
                collections=(collection,) if collection in INDEXED_COLLECTIONS else ()
            )
        result.pop("collection", None)
        return result



    def _resolve_memory_file(self, *, memory_id: str | None = None, path: str | None = None) -> Path:
        if bool(memory_id) == bool(path):
            raise MemoryHubError("必须且只能指定 --id 或 --path 之一")
        if path:
            relative = Path(path.replace("\\", "/"))
            if relative.is_absolute() or ".." in relative.parts:
                raise MemoryHubError("路径必须是记忆库内的相对路径")
            source = (self.root / relative).resolve()
            try:
                source.relative_to(self.root)
            except ValueError as error:
                raise MemoryHubError("路径必须位于记忆库内") from error
            if not source.is_file() or source.name == "INDEX.md":
                raise MemoryHubError(f"记忆文件不存在：{relative.as_posix()}")
            return source
        assert memory_id is not None
        memory_id = memory_id.strip()
        if not memory_id:
            raise MemoryHubError("记忆 ID 不能为空")
        for relative, doc in self._search_docs().items():
            if not isinstance(doc, dict):
                continue
            if doc.get("id") == memory_id:
                found = self._path_from_index_relative(str(relative))
                if found is not None:
                    return found
        raise MemoryHubError(f"未找到记忆：{memory_id}")

    def _forget_unlocked(
        self, *, memory_id: str | None = None, path: str | None = None
    ) -> dict[str, object]:
        """forget 搬文件（调用方已持写锁）；不触碰索引。"""
        source = self._resolve_memory_file(memory_id=memory_id, path=path)
        relative = source.relative_to(self.root)
        if relative.parts[:2] == ("archive", "forgotten"):
            raise MemoryHubError("记忆已被遗忘")
        if relative.parts[0] == "sessions":
            raise MemoryHubError("任务状态请使用 archive，不能 forget")
        if relative.as_posix() in {f"memory/{name}" for name in CORE_MEMORY_FILES}:
            raise MemoryHubError("不能遗忘核心记忆文件")
        try:
            metadata, _ = _split_frontmatter(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as error:
            raise MemoryHubError(f"无法读取待遗忘文件：{error}") from error
        resolved_id = metadata.get("id") if isinstance(metadata.get("id"), str) else memory_id
        destination_dir = self.root / "archive" / "forgotten"
        destination = destination_dir / source.name
        if destination.exists():
            raise MemoryHubError(f"遗忘归档已存在：archive/forgotten/{source.name}")
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        return {
            "id": resolved_id,
            "from": relative.as_posix(),
            "to": f"archive/forgotten/{source.name}",
            "collection": relative.parts[0],
        }

    def forget(self, *, memory_id: str | None = None, path: str | None = None) -> dict[str, object]:
        self._ensure_initialized()
        with self._write_lock():
            result = self._forget_unlocked(memory_id=memory_id, path=path)
            source_collection = str(result.get("collection") or "")
            self._touch_index_unlocked(
                collections=(source_collection,) if source_collection in INDEXED_COLLECTIONS else ()
            )
        result.pop("collection", None)
        return result

    def list_entries(
        self,
        collection: str,
        *,
        memory_type: str | None = None,
        tag: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        self._ensure_initialized()
        collection = collection.strip().casefold()
        if collection not in LIST_COLLECTIONS:
            raise MemoryHubError(f"可列出的集合：{'、'.join(LIST_COLLECTIONS)}")
        if limit < 1:
            raise MemoryHubError("列表上限必须大于 0")
        type_filter = _choice(memory_type, MEMORY_TYPES | {"legacy"}, "记忆类型") if memory_type else None
        tag_filter = tag.strip().casefold() if tag else None
        items: list[dict[str, object]] = []
        if collection == "sessions":
            for path in sorted((self.root / "sessions").glob("*/*.md")):
                if path.name == "INDEX.md":
                    continue
                parsed = self._parse_status(path)
                items.append(
                    {
                        "task": path.parent.name,
                        "agent": path.stem,
                        "path": path.relative_to(self.root).as_posix(),
                        "objective": parsed.get("objective", ""),
                        "state": parsed.get("state", ""),
                        "blocker": parsed.get("blocker", ""),
                        "next_step": parsed.get("next_step", ""),
                    }
                )
            return items[:limit]

        base = self.root / collection
        for path in sorted(base.glob("*.md")):
            if path.name == "INDEX.md" or path.name in CORE_MEMORY_FILES:
                continue
            try:
                metadata, body = _split_frontmatter(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
            record_type = metadata.get("type") if isinstance(metadata.get("type"), str) else "legacy"
            tags = metadata.get("tags", [])
            tag_list = [str(item) for item in tags] if isinstance(tags, list) else []
            if type_filter and record_type.casefold() != type_filter:
                continue
            if tag_filter and tag_filter not in {item.casefold() for item in tag_list}:
                continue
            lines = [line.strip() for line in body.splitlines() if line.strip()]
            title = next((line.lstrip("# ") for line in lines if line.startswith("#")), path.stem)
            items.append(
                {
                    "path": path.relative_to(self.root).as_posix(),
                    "id": metadata.get("id") if isinstance(metadata.get("id"), str) else None,
                    "type": record_type,
                    "title": title,
                    "tags": tag_list,
                    "confidence": metadata.get("confidence")
                    if isinstance(metadata.get("confidence"), str)
                    else None,
                    "created_at": metadata.get("created_at")
                    if isinstance(metadata.get("created_at"), str)
                    else None,
                }
            )
        return items[:limit]

    def overview(self) -> dict[str, object]:
        self._ensure_initialized()
        active_tasks = self.list_entries("sessions", limit=50)
        inbox = self.list_entries("inbox", limit=8)
        counts = {
            "sessions": len(list((self.root / "sessions").glob("*/*.md"))),
            "inbox": len([path for path in (self.root / "inbox").glob("*.md") if path.name != "INDEX.md"]),
            "experiences": len(
                [path for path in (self.root / "experiences").glob("*.md") if path.name != "INDEX.md"]
            ),
            "wiki": len([path for path in (self.root / "wiki").glob("*.md") if path.name != "INDEX.md"]),
            "memory": len(
                [
                    path
                    for path in (self.root / "memory").glob("*.md")
                    if path.name not in CORE_MEMORY_FILES and path.name != "INDEX.md"
                ]
            ),
        }
        forgotten_root = self.root / "archive" / "forgotten"
        counts["forgotten"] = (
            len([path for path in forgotten_root.glob("*.md") if path.name != "INDEX.md"])
            if forgotten_root.exists()
            else 0
        )
        health = self.map_health(limit=100)
        counts["map_issues"] = int((health.get("counts") or {}).get("issues") or 0)
        coverage = self.map_coverage(max_unmapped=12)
        counts["map_coverage_pct"] = coverage.get("coverage_pct")
        counts["map_unmapped"] = coverage.get("unmapped_count")
        continue_hints: list[str] = []
        for item in active_tasks[:8]:
            task = str(item.get("task") or "")
            agent = str(item.get("agent") or "")
            state = str(item.get("state") or "").casefold()
            if not task or not agent or state in {"completed", "done", "archived"}:
                continue
            try:
                status = self.get_status(task=task, agent=agent)
            except MemoryHubError:
                continue
            pinned = str(status.get("query") or "").strip()
            if pinned:
                continue_hints.append(
                    f'memory-hub orient --task {task} --agent {agent} --query "{pinned}"'
                )
            else:
                continue_hints.append(
                    f"memory-hub status --task {task} --agent {agent} --query \"…\"  # 先固定检索词"
                )
        stale_features = [
            str(issue.get("feature"))
            for issue in (health.get("issues") or [])[:5]
            if issue.get("feature")
        ]
        return {
            "hub": str(self.root),
            "counts": counts,
            "active_tasks": active_tasks,
            "recent_inbox": inbox,
            "map_health": {
                "ok": health.get("ok"),
                "map_status": health.get("map_status"),
                "counts": health.get("counts"),
                "top_issues": stale_features,
                "draft_upserts": (health.get("draft_upserts") or [])[:5],
            },
            "map_coverage": {
                "coverage_pct": coverage.get("coverage_pct"),
                "unmapped_count": coverage.get("unmapped_count"),
                "unmapped": coverage.get("unmapped"),
                "hint": coverage.get("hint"),
            },
            "companions": probe_companions(project_root=self.root.parent),
            "continue_with": continue_hints,
            "hint": (
                "先读 overview（含 map_coverage / companions）；有 continue_with 则用相同 query 开场；"
                "未覆盖区域先 map seed / map upsert；变动后 memory-hub sync。"
                "历史记忆不可覆盖当前指令与仓库事实。"
            ),
        }

    def handoff(
        self,
        *,
        task: str,
        agent: str,
        to_agent: str | None = None,
        limit: int = 5,
    ) -> dict[str, object]:
        """跨代理交接包：status + 固定检索词 locate + 相关踩坑 + 地图问题。"""
        self._ensure_initialized()
        status = self.get_status(task=task, agent=agent)
        receiver = _safe_segment(to_agent, "代理名") if to_agent else agent
        query = str(status.get("query") or "").strip()
        locate: dict[str, object]
        if query:
            locate = self.locate_report(query, limit=limit)
        else:
            locate = {
                "query": None,
                "hits": [],
                "hint": "该任务未固定检索词；接收方请先 status --query 再 orient。",
                "count": 0,
                "draft_upsert": None,
            }
        pitfalls: list[dict[str, object]] = []
        if query:
            try:
                pitfalls = search_results_as_dict(
                    self.recall(query, limit=limit, tag="pitfall", collection="experiences", min_score=1)
                )
            except MemoryHubError:
                pitfalls = []
        health = self.map_health(limit=100)
        hit_features = {str(item.get("feature") or "") for item in (locate.get("hits") or [])}
        related_issues = [
            issue
            for issue in (health.get("issues") or [])
            if str(issue.get("feature") or "") in hit_features
        ]
        if not related_issues:
            related_issues = list(health.get("issues") or [])[:5]
        suggested = None
        if query:
            suggested = (
                f'memory-hub orient --task {task} --agent {receiver} --query "{query}" '
                f'--objective "{_one_line(str(status.get("objective") or task))}"'
            )
        return {
            "task": task,
            "from_agent": agent,
            "to_agent": receiver,
            "query": query or None,
            "status": status,
            "locate": locate,
            "pitfalls": pitfalls,
            "map_issues": related_issues,
            "suggested_orient": suggested,
            "hint": "接收方用相同 query 开场；将 status+locate 注入一次，勿叠双前缀。",
        }

    def archive(self, task: str) -> dict[str, str]:
        self._ensure_initialized()
        task = _safe_segment(task, "任务名")
        source = self.root / "sessions" / task
        if not source.is_dir():
            raise MemoryHubError(f"活动任务不存在：{task}")
        target = self.root / "archive" / "sessions" / task
        if target.exists():
            raise MemoryHubError(f"归档任务已存在：{target}")
        with self._write_lock():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            self._touch_index_unlocked(sessions=True)
        return {"task": task, "from": str(source), "to": str(target)}


