"""检索索引与集合 INDEX 维护。"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from . import search_index as _search_index
from .constants import COLLECTIONS, CORE_MEMORY_FILES, INDEXED_COLLECTIONS
from .maps import _parse_map_fields
from .util import atomic_write, now, one_line, split_frontmatter, tokenize_query

_CORE_RELATIVES = frozenset(f"memory/{name}" for name in CORE_MEMORY_FILES)


class IndexMixin:
    """search-index / INDEX.md / reindex / stats（混入 MemoryHub）。"""

    def reindex(self) -> dict[str, int]:
        self._ensure_initialized()
        with self._write_lock():
            return self._reindex_unlocked()

    def _search_index_file(self) -> Path:
        return _search_index.search_index_path(self.root)

    def _search_dirty_path(self) -> Path:
        return _search_index.dirty_marker_path(self.root)

    def _mark_search_dirty(self) -> None:
        self._search_docs_cache = None
        try:
            path = self._search_dirty_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        except OSError:
            pass

    def _clear_search_dirty(self) -> None:
        try:
            self._search_dirty_path().unlink(missing_ok=True)
        except OSError:
            pass

    def _cache_search_docs(self, docs: dict[str, object], watermark: dict[str, int]) -> None:
        self._search_docs_cache = (docs, watermark)

    def _search_docs(self) -> dict[str, object]:
        dirty = self._search_dirty_path().is_file()
        if dirty:
            self._search_docs_cache = None
        else:
            cached = self._search_docs_cache
            if cached is not None:
                docs, watermark = cached
                try:
                    current = _search_index.compute_source_watermark(self.root)
                    if _search_index.watermark_matches(
                        {
                            "source_count": watermark["source_count"],
                            "source_max_mtime_ns": watermark["source_max_mtime_ns"],
                        },
                        current,
                    ):
                        return docs
                except OSError:
                    pass
                self._search_docs_cache = None

        index_file = self._search_index_file()
        payload = _search_index.load_index(index_file)
        docs = payload.get("docs")
        fresh = (
            not dirty
            and isinstance(docs, dict)
            and bool(docs)
            and int(payload.get("version") or 0) == _search_index.SEARCH_INDEX_VERSION
        )
        watermark: dict[str, int] | None = None
        if fresh:
            try:
                watermark = _search_index.compute_source_watermark(self.root)
                fresh = _search_index.watermark_matches(payload, watermark)
            except OSError:
                fresh = False
                watermark = None
        if fresh and isinstance(docs, dict) and watermark is not None:
            self._cache_search_docs(docs, watermark)
            return docs
        built = self._build_search_docs_unlocked()
        # 读路径尽力落盘（可再生，允许竞态）
        try:
            self._write_search_index_unlocked(built)
        except OSError:
            try:
                self._cache_search_docs(built, _search_index.compute_source_watermark(self.root))
            except OSError:
                self._search_docs_cache = None
        return built

    def _build_search_docs_unlocked(self) -> dict[str, object]:
        docs: dict[str, object] = {}
        for path in self.root.rglob("*.md"):
            if path.name == "INDEX.md":
                continue
            relative = path.relative_to(self.root)
            if any(part in {"node_modules", ".git", "meta"} for part in relative.parts):
                continue
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            metadata, body = split_frontmatter(content)
            relative_posix = relative.as_posix()
            docs[relative_posix] = _search_index.build_doc(
                relative=relative_posix,
                metadata=metadata,
                body=body,
                tokenize=tokenize_query,
                parse_map_fields=_parse_map_fields,
            )
        return docs

    def _write_search_index_unlocked(self, docs: dict[str, object] | None = None) -> int:
        resolved = docs if docs is not None else self._build_search_docs_unlocked()
        watermark = _search_index.compute_source_watermark(self.root)
        payload = {
            "version": _search_index.SEARCH_INDEX_VERSION,
            "built_at": now().isoformat(timespec="seconds"),
            "docs": resolved,
            "source_count": watermark["source_count"],
            "source_max_mtime_ns": watermark["source_max_mtime_ns"],
        }
        _search_index.save_index(self._search_index_file(), payload, atomic_write=atomic_write)
        self._clear_search_dirty()
        self._cache_search_docs(resolved, watermark)
        return len(resolved)

    def _count_collection_files(self, collection: str) -> int:
        base = self.root / collection
        if not base.is_dir():
            return 0
        return len([path for path in base.glob("*.md") if path.name != "INDEX.md"])

    def _write_collection_index(self, collection: str, timestamp: str) -> int:
        base = self.root / collection
        base.mkdir(parents=True, exist_ok=True)
        files = sorted(path for path in base.glob("*.md") if path.name != "INDEX.md")
        lines = [f"# {collection.title()} Index", "", f"Updated: {timestamp}", ""]
        lines.extend(f"- [{path.stem}]({path.name})" for path in files)
        atomic_write(base / "INDEX.md", "\n".join(lines).rstrip() + "\n")
        return len(files)

    def _session_overview(self) -> tuple[int, int, list[str], list[str]]:
        active_root = self.root / "sessions"
        archived_root = self.root / "archive" / "sessions"
        active = sorted(path for path in active_root.glob("*/*.md") if path.name != "INDEX.md") if active_root.is_dir() else []
        archived = sorted(archived_root.glob("*/*.md")) if archived_root.exists() else []
        session_lines: list[str] = []
        session_digest: list[str] = []
        for path in active:
            parsed = self._parse_status(path)
            objective = one_line(str(parsed.get("objective", ""))) or path.parent.name
            state = one_line(str(parsed.get("state", ""))) or "unknown"
            session_lines.append(
                f"- [{path.parent.name}/{path.stem}]({path.relative_to(active_root).as_posix()})"
                f" — {state} — {objective}"
            )
            session_digest.append(
                f"- `{path.parent.name}` / `{path.stem}`: **{state}** — {objective}"
            )
        return len(active), len(archived), session_lines, session_digest

    def _write_sessions_index(
        self,
        timestamp: str,
        *,
        session_lines: Sequence[str],
        archived: Sequence[Path],
    ) -> None:
        active_root = self.root / "sessions"
        archived_root = self.root / "archive" / "sessions"
        active_root.mkdir(parents=True, exist_ok=True)
        lines = ["# Sessions Index", "", f"Updated: {timestamp}", "", "## 活动任务", ""]
        lines.extend(session_lines)
        lines.extend(["", "## 已完成/归档任务", ""])
        lines.extend(
            f"- [{path.parent.name}/{path.stem}](../archive/sessions/{path.relative_to(archived_root).as_posix()})"
            for path in archived
        )
        atomic_write(active_root / "INDEX.md", "\n".join(lines).rstrip() + "\n")

    def _write_root_index(
        self,
        timestamp: str,
        counts: dict[str, int],
        session_digest: Sequence[str],
    ) -> None:
        root_lines = [
            "# AI Memory Hub",
            "",
            f"Updated: {timestamp}",
            "",
            "## 活动任务速览",
            "",
        ]
        if session_digest:
            root_lines.extend(session_digest)
        else:
            root_lines.append("- （无活动任务）")
        root_lines.extend(
            [
                "",
                "## Core Memory",
                "",
                "- [CORE](memory/CORE.md)",
                "- [LESSONS](memory/LESSONS.md)",
                "- [USER](memory/USER.md)",
                "- [AGENTS](memory/AGENTS.md)",
                "",
                "## Collections",
                "",
                f"- [wiki](wiki/INDEX.md): {counts['wiki']} entries",
                f"- [experiences](experiences/INDEX.md): {counts['experiences']} entries",
                f"- [sessions](sessions/INDEX.md): {counts['sessions']} active records, "
                f"{counts['archived_sessions']} archived records",
                f"- [inbox](inbox/INDEX.md): {counts['inbox']} entries",
                "",
                "> 其他 AI/脚本：先读本 INDEX 与 `memory-hub overview`，再用 recall/context；"
                "写操作必须走 CLI 以获取写锁，勿手工并发改同一文件。",
            ]
        )
        atomic_write(self.root / "INDEX.md", "\n".join(root_lines) + "\n")

    def _touch_index_unlocked(
        self,
        *,
        collections: Sequence[str] = (),
        sessions: bool = False,
    ) -> dict[str, int]:
        """增量更新索引：只重写受影响集合与根 INDEX；sessions 变更时同步 sessions/INDEX。"""
        timestamp = now().isoformat(timespec="seconds")
        touched = {name for name in collections if name in INDEXED_COLLECTIONS}
        counts: dict[str, int] = {}
        for name in INDEXED_COLLECTIONS:
            if name in touched:
                counts[name] = self._write_collection_index(name, timestamp)
            else:
                counts[name] = self._count_collection_files(name)

        active_count, archived_count, session_lines, session_digest = self._session_overview()
        counts["sessions"] = active_count
        counts["archived_sessions"] = archived_count
        if sessions:
            archived_root = self.root / "archive" / "sessions"
            archived = sorted(archived_root.glob("*/*.md")) if archived_root.exists() else []
            self._write_sessions_index(
                timestamp,
                session_lines=session_lines,
                archived=archived,
            )
        self._write_root_index(timestamp, counts, session_digest)
        # 增量写只标脏；下次 recall/locate/_find_by_key 再重建 search-index
        self._mark_search_dirty()
        counts["search_docs"] = -1
        return counts

    def _reindex_unlocked(self) -> dict[str, int]:
        timestamp = now().isoformat(timespec="seconds")
        counts: dict[str, int] = {}
        for collection in INDEXED_COLLECTIONS:
            counts[collection] = self._write_collection_index(collection, timestamp)

        active_count, archived_count, session_lines, session_digest = self._session_overview()
        counts["sessions"] = active_count
        counts["archived_sessions"] = archived_count
        archived_root = self.root / "archive" / "sessions"
        archived = sorted(archived_root.glob("*/*.md")) if archived_root.exists() else []
        self._write_sessions_index(
            timestamp,
            session_lines=session_lines,
            archived=archived,
        )
        self._write_root_index(timestamp, counts, session_digest)
        counts["search_docs"] = self._write_search_index_unlocked()
        return counts

    def stats(self) -> dict[str, object]:
        """统计优先走 search-index；仅对未入索引文件做点读以发现 unreadable。"""
        self._ensure_initialized()
        docs = self._search_docs()
        by_collection = {name: 0 for name in COLLECTIONS}
        by_type: dict[str, int] = {}
        records = 0
        metadata_records = 0
        relations = 0
        indexed: set[str] = set()

        for relative, doc in docs.items():
            if not isinstance(doc, dict):
                continue
            rel = str(relative).replace("\\", "/")
            indexed.add(rel)
            if rel in _CORE_RELATIVES:
                continue
            records += 1
            collection = str(doc.get("collection") or "")
            if collection in by_collection:
                by_collection[collection] += 1
            memory_type = str(doc.get("type") or "legacy")
            by_type[memory_type] = by_type.get(memory_type, 0) + 1
            if doc.get("has_frontmatter"):
                metadata_records += 1
            edges = doc.get("link_edges")
            if isinstance(edges, list):
                relations += len(edges)
            else:
                links = doc.get("links")
                if isinstance(links, list):
                    relations += len(links)

        unreadable_records = 0
        markdown_files = 0
        index_files = 0
        for path in self.root.rglob("*.md"):
            markdown_files += 1
            if path.name == "INDEX.md":
                index_files += 1
                continue
            try:
                relative = path.relative_to(self.root)
            except ValueError:
                continue
            if any(part in {"node_modules", ".git", "meta"} for part in relative.parts):
                continue
            rel = relative.as_posix()
            if rel in indexed or rel in _CORE_RELATIVES:
                continue
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                unreadable_records += 1
                by_type["unreadable"] = by_type.get("unreadable", 0) + 1
                records += 1
                collection = relative.parts[0] if relative.parts else ""
                if collection in by_collection:
                    by_collection[collection] += 1

        coverage = round(metadata_records * 100 / records, 1) if records else 100.0
        active_sessions = len(list((self.root / "sessions").glob("*/*.md")))
        archived_root = self.root / "archive" / "sessions"
        archived_sessions = len(list(archived_root.glob("*/*.md"))) if archived_root.exists() else 0
        return {
            "hub": str(self.root),
            "markdown_files": markdown_files,
            "index_files": index_files,
            "records": records,
            "metadata_records": metadata_records,
            "metadata_coverage": coverage,
            "relations": relations,
            "by_type": dict(sorted(by_type.items())),
            "by_collection": by_collection,
            "active_sessions": active_sessions,
            "archived_sessions": archived_sessions,
            "unreadable_records": unreadable_records,
        }
