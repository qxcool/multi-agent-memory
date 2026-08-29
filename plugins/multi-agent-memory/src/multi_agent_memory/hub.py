from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Sequence


COLLECTIONS = ("memory", "sessions", "experiences", "wiki", "inbox", "archive")
STATUS_FIELDS = {
    "目标": "objective",
    "步骤": "steps",
    "已完成": "completed",
    "当前状态": "state",
    "阻塞": "blocker",
    "下一步": "next_step",
}


class MemoryHubError(RuntimeError):
    """记忆库操作失败。"""


@dataclass(frozen=True)
class SearchResult:
    path: str
    score: int
    title: str
    snippet: str


def _now() -> datetime:
    return datetime.now().astimezone()


def _one_line(value: str) -> str:
    return " ".join(value.replace("\x00", "").split())


def _safe_segment(value: str, label: str) -> str:
    value = value.strip()
    if not value or value in {".", ".."}:
        raise MemoryHubError(f"{label}不能为空")
    if any(char in value for char in ("/", "\\", "\x00")):
        raise MemoryHubError(f"{label}不能包含路径分隔符")
    if any(ord(char) < 32 for char in value):
        raise MemoryHubError(f"{label}不能包含控制字符")
    return value


def _slug(value: str, fallback: str = "note") -> str:
    value = re.sub(r"[^\w\-\u4e00-\u9fff]+", "-", value, flags=re.UNICODE)
    return value.strip("-")[:60] or fallback


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


class HubLock:
    def __init__(self, root: Path, timeout: float = 10.0, stale_after: float = 120.0):
        self.path = root / ".memory-hub.lock"
        self.timeout = timeout
        self.stale_after = stale_after
        self.acquired = False

    def __enter__(self) -> "HubLock":
        deadline = time.monotonic() + self.timeout
        payload = json.dumps({"pid": os.getpid(), "created": time.time()})
        while True:
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write(payload)
                self.acquired = True
                return self
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                    if age > self.stale_after:
                        self.path.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise MemoryHubError(f"等待记忆库写锁超时：{self.path}")
                time.sleep(0.05)

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.acquired:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


class MemoryHub:
    """以 Markdown 文件为存储介质的本地共享记忆库。"""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()

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
            core_files = {
                "memory/CORE.md": "# Core Memory\n\n记录长期稳定的项目事实、约束和架构决策。\n",
                "memory/USER.md": "# User Memory\n\n仅记录用户明确要求长期保留的偏好。\n",
                "memory/AGENTS.md": "# Agent Memory\n\n记录代理协作约定、角色和交接规则。\n",
            }
            for relative, content in core_files.items():
                path = self.root / relative
                if not path.exists():
                    _atomic_write(path, content)
                    created.append(relative)
            ignore = self.root / ".gitignore"
            if not track and not ignore.exists():
                _atomic_write(ignore, "*\n!.gitignore\n")
                created.append(".gitignore")
            self._reindex_unlocked()
        return {"hub": str(self.root), "created": created, "tracked": track}

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
    ) -> dict[str, object]:
        self._ensure_initialized()
        task = _safe_segment(task, "任务名")
        agent = _safe_segment(agent, "代理名")
        path = self.root / "sessions" / task / f"{agent}.md"
        previous = self._parse_status(path) if path.exists() else {}
        values: dict[str, object] = {
            "objective": objective if objective is not None else previous.get("objective", ""),
            "steps": steps if steps is not None else previous.get("steps", ""),
            "completed": list(completed) if completed else previous.get("completed", []),
            "state": state if state is not None else previous.get("state", "in-progress"),
            "blocker": blocker if blocker is not None else previous.get("blocker", "无"),
            "next_step": next_step if next_step is not None else previous.get("next_step", ""),
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
        )
        with self._write_lock():
            _atomic_write(path, body)
            self._reindex_unlocked()
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

    def remember(self, *, agent: str, text: str, tags: Sequence[str] = ()) -> dict[str, object]:
        self._ensure_initialized()
        agent = _safe_segment(agent, "代理名")
        text = text.strip()
        if not text:
            raise MemoryHubError("记忆内容不能为空")
        now = _now()
        stem = f"{now:%Y%m%d-%H%M%S}-{_slug(agent)}-{_slug(text[:32])}"
        clean_tags = [_one_line(tag) for tag in tags if tag.strip()]
        with self._write_lock():
            path = self.root / "inbox" / f"{stem}.md"
            counter = 1
            while path.exists():
                path = self.root / "inbox" / f"{stem}-{counter}.md"
                counter += 1
            body = (
                f"# {_one_line(text)[:80]}\n\n"
                f"- Agent: {agent}\n"
                f"- Created: {now.isoformat(timespec='seconds')}\n"
                f"- Tags: {', '.join(clean_tags)}\n\n"
                f"{text.rstrip()}\n"
            )
            _atomic_write(path, body)
            self._reindex_unlocked()
        return {"path": str(path), "agent": agent, "tags": clean_tags}

    def recall(self, query: str, *, limit: int = 10, include_archive: bool = True) -> list[SearchResult]:
        self._ensure_initialized()
        query = query.strip()
        if not query:
            raise MemoryHubError("检索词不能为空")
        terms = list(dict.fromkeys(term.casefold() for term in re.findall(r"[^\s,，;；]+", query)))
        results: list[SearchResult] = []
        for path in self.root.rglob("*.md"):
            if path.name == "INDEX.md":
                continue
            relative = path.relative_to(self.root)
            if not include_archive and relative.parts and relative.parts[0] == "archive":
                continue
            if any(part in {"node_modules", ".git"} for part in relative.parts):
                continue
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            lowered = content.casefold()
            path_text = str(relative).casefold()
            hits = [lowered.count(term) for term in terms]
            if not any(hits):
                continue
            score = sum(count * 3 for count in hits) + sum(5 for term in terms if term in path_text)
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            title = next((line.lstrip("# ") for line in lines if line.startswith("#")), relative.stem)
            matching = next((line for line in lines if any(term in line.casefold() for term in terms)), lines[0])
            results.append(SearchResult(str(relative).replace("\\", "/"), score, title, matching[:280]))
        results.sort(key=lambda item: (-item.score, item.path))
        return results[: max(1, limit)]

    def context(self, query: str | None = None, *, max_chars: int = 12000) -> str:
        self._ensure_initialized()
        sections: list[str] = []
        for name in ("CORE.md", "USER.md", "AGENTS.md"):
            path = self.root / "memory" / name
            if path.exists():
                sections.append(path.read_text(encoding="utf-8").strip())
        if query:
            for result in self.recall(query, limit=8, include_archive=False):
                sections.append(f"## {result.path}\n\n{result.snippet}")
        return "\n\n---\n\n".join(sections)[:max_chars]

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
            self._reindex_unlocked()
        return {"task": task, "from": str(source), "to": str(target)}

    def reindex(self) -> dict[str, int]:
        self._ensure_initialized()
        with self._write_lock():
            return self._reindex_unlocked()

    def _reindex_unlocked(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        timestamp = _now().isoformat(timespec="seconds")
        for collection in ("wiki", "experiences", "inbox"):
            base = self.root / collection
            files = sorted(path for path in base.glob("*.md") if path.name != "INDEX.md")
            counts[collection] = len(files)
            lines = [f"# {collection.title()} Index", "", f"Updated: {timestamp}", ""]
            lines.extend(f"- [{path.stem}]({path.name})" for path in files)
            _atomic_write(base / "INDEX.md", "\n".join(lines).rstrip() + "\n")

        active_root = self.root / "sessions"
        archived_root = self.root / "archive" / "sessions"
        active = sorted(path for path in active_root.glob("*/*.md") if path.name != "INDEX.md")
        archived = sorted(archived_root.glob("*/*.md")) if archived_root.exists() else []
        counts["sessions"] = len(active)
        counts["archived_sessions"] = len(archived)
        lines = ["# Sessions Index", "", f"Updated: {timestamp}", "", "## 活动任务", ""]
        lines.extend(f"- [{path.parent.name}/{path.stem}]({path.relative_to(active_root).as_posix()})" for path in active)
        lines.extend(["", "## 已完成/归档任务", ""])
        lines.extend(
            f"- [{path.parent.name}/{path.stem}](../archive/sessions/{path.relative_to(archived_root).as_posix()})"
            for path in archived
        )
        _atomic_write(active_root / "INDEX.md", "\n".join(lines).rstrip() + "\n")

        root_lines = [
            "# AI Memory Hub",
            "",
            f"Updated: {timestamp}",
            "",
            "## Core Memory",
            "",
            "- [CORE](memory/CORE.md)",
            "- [USER](memory/USER.md)",
            "- [AGENTS](memory/AGENTS.md)",
            "",
            "## Collections",
            "",
            f"- [wiki](wiki/INDEX.md): {counts['wiki']} entries",
            f"- [experiences](experiences/INDEX.md): {counts['experiences']} entries",
            f"- [sessions](sessions/INDEX.md): {counts['sessions']} active records, {counts['archived_sessions']} archived records",
            f"- [inbox](inbox/INDEX.md): {counts['inbox']} entries",
        ]
        _atomic_write(self.root / "INDEX.md", "\n".join(root_lines) + "\n")
        return counts

    def doctor(self) -> dict[str, object]:
        issues: list[str] = []
        if not self.root.exists():
            issues.append("记忆库目录不存在")
            return {"ok": False, "hub": str(self.root), "issues": issues}
        for name in COLLECTIONS:
            path = self.root / name
            if not path.is_dir():
                issues.append(f"缺少目录：{name}")
        lock = self.root / ".memory-hub.lock"
        if lock.exists() and time.time() - lock.stat().st_mtime > 120:
            issues.append("存在超过两分钟的陈旧写锁")
        markdown_count = 0
        for path in self.root.rglob("*.md"):
            markdown_count += 1
            try:
                path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                issues.append(f"文件不是有效 UTF-8：{path.relative_to(self.root)}")
            except OSError as error:
                issues.append(f"无法读取：{path.relative_to(self.root)}（{error}）")
        return {
            "ok": not issues,
            "hub": str(self.root),
            "markdown_files": markdown_count,
            "issues": issues,
        }


def search_results_as_dict(results: Sequence[SearchResult]) -> list[dict[str, object]]:
    return [asdict(result) for result in results]
