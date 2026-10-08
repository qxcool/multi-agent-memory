"""功能地图：指纹、locate、coverage、health、seed。"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Sequence

from .constants import CONFIDENCE_LEVELS, CONFIDENCE_SCORE_ADJUST, RELATION_TYPES
from .errors import MemoryHubError
from .util import (
    atomic_write,
    choice,
    content_fingerprint,
    frontmatter,
    normalize_memory_key,
    now,
    one_line,
    safe_segment,
    slug,
    split_frontmatter,
    tokenize_query,
    _LATIN_TOKEN,
)

PROJECT_SCAN_SKIP = {
    ".git",
    ".hg",
    ".svn",
    ".ai-memory-hub",
    ".worktree",
    ".worktrees",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "coverage",
    ".tox",
    ".idea",
    ".vscode",
    ".cursor",
    ".agents",
    ".claude",
    ".codex",
    ".qoder",
    ".opencode",
    "target",
    "vendor",
}
# 地图 paths 禁止写入/巡检的路径段（工作树副本、VCS、依赖与缓存）
MAP_PATH_SKIP_PARTS = frozenset(
    {
        ".worktree",
        ".worktrees",
        ".git",
        ".hg",
        ".svn",
        ".ai-memory-hub",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
    }
)
SOURCE_FILE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".cs",
    ".md",
    ".ps1",
    ".sh",
}
LOCATE_MISS_HINT = (
    "未命中功能地图。请先 map upsert 写入该功能的 paths；"
    "勿直接全仓 rg/Glob。架构溯源可用 GitNexus。"
)
LOCATE_HIT_HINT = "已命中功能地图：优先打开返回的 paths/commands，勿全仓 rg/Glob。"
RELATED_MAP_SCORE_FLOOR = 4


_MAX_PATH_FINGERPRINT_BYTES = 2 * 1024 * 1024


def _is_disallowed_repo_path(relative: str) -> bool:
    """工作树/VCS/依赖等路径段不得写入功能地图。"""
    parts = Path(str(relative).strip().replace("\\", "/")).parts
    return any(part in MAP_PATH_SKIP_PARTS for part in parts)


def _repo_file_fingerprint(project_root: Path, relative: str) -> str | None:
    """仓库相对路径内容指纹；缺失或不可读返回 None。大文件用 size+mtime。"""
    if _is_disallowed_repo_path(relative):
        return None
    try:
        root = project_root.resolve()
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            return None
        if not path.is_file():
            return None
        size = path.stat().st_size
        if size > _MAX_PATH_FINGERPRINT_BYTES:
            stamp = f"meta:{size}:{path.stat().st_mtime_ns}"
            return hashlib.sha256(stamp.encode("utf-8")).hexdigest()[:16]
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def _inspect_map_paths(
    project_root: Path,
    paths: Sequence[str],
    fingerprints: dict[str, str] | None = None,
) -> dict[str, list[str]]:
    """检查地图路径：missing=不存在；drifted=存在但与记录指纹不一致。"""
    recorded = fingerprints or {}
    missing: list[str] = []
    drifted: list[str] = []
    for raw in paths:
        rel = str(raw).strip().replace("\\", "/")
        if not rel or _is_disallowed_repo_path(rel):
            continue
        target = project_root / rel
        if not target.exists():
            missing.append(rel)
            continue
        expected = recorded.get(rel)
        if expected is None:
            # 兼容旧地图：无指纹则不报漂移
            continue
        actual = _repo_file_fingerprint(project_root, rel)
        if actual is None or actual != expected:
            drifted.append(rel)
    return {"missing": missing, "drifted": drifted}


def _path_fingerprints_for(
    project_root: Path,
    paths: Sequence[str],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in paths:
        rel = str(raw).strip().replace("\\", "/")
        if not rel or _is_disallowed_repo_path(rel):
            continue
        fingerprint = _repo_file_fingerprint(project_root, rel)
        if fingerprint is not None:
            result[rel] = fingerprint
    return result


def _file_paths_missing_fingerprint(
    project_root: Path,
    paths: Sequence[str],
    fingerprints: dict[str, str] | None = None,
) -> list[str]:
    """仅文件路径需要内容指纹；目录入口（如 docs/）不报缺指纹。"""
    recorded = fingerprints or {}
    missing: list[str] = []
    for raw in paths:
        rel = str(raw).strip().replace("\\", "/")
        if not rel or rel in recorded or _is_disallowed_repo_path(rel):
            continue
        target = project_root / rel
        if target.is_file():
            missing.append(rel)
    return missing


def _normalize_path_fingerprints(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, item in value.items():
        rel = str(key).strip().replace("\\", "/")
        if not rel or _is_disallowed_repo_path(rel):
            continue
        if isinstance(item, str) and item.strip():
            result[rel] = item.strip()
    return result



def _normalize_feature_name(value: str) -> str:
    text = one_line(value)
    if not text:
        raise MemoryHubError("功能名不能为空")
    if any(char in text for char in ("/", "\\", "\x00")):
        raise MemoryHubError("功能名不能包含路径分隔符")
    if text.casefold().startswith("feature:"):
        text = text.split(":", 1)[1].strip()
    if not text:
        raise MemoryHubError("功能名不能为空")
    if len(text) > 80:
        raise MemoryHubError("功能名过长（最多 80 字符）")
    return text


def _strip_worktree_prefix(text: str) -> str:
    """`.worktree/<名>/…` / `.worktrees/<名>/…` → 主仓相对路径；locate/upsert 共用。"""
    parts = Path(text.replace("\\", "/")).parts
    if len(parts) >= 3 and parts[0].casefold() in {".worktree", ".worktrees"}:
        return "/".join(parts[2:])
    return text


def _normalize_repo_path(value: str) -> str:
    text = value.strip().replace("\\", "/").rstrip("/")
    if not text:
        raise MemoryHubError("路径不能为空")
    if text.startswith("/") or re.match(r"^[a-zA-Z]:/", text):
        raise MemoryHubError("路径必须是仓库相对路径")
    parts = Path(text).parts
    if ".." in parts:
        raise MemoryHubError("路径不能包含 ..")
    # Agent 在工作树里可传 .worktree/<名>/src/…；入库只留主仓相对路径
    text = _strip_worktree_prefix(text)
    if not text:
        raise MemoryHubError("工作树前缀剥离后路径为空")
    parts = Path(text).parts
    if any(part in MAP_PATH_SKIP_PARTS for part in parts):
        raise MemoryHubError(
            "路径不能指向工作树/依赖/缓存目录（如 .git、node_modules；"
            "请用主仓相对路径，或 .worktree/<名>/… 由 CLI 自动剥离）"
        )
    return text


def _suggest_feature_slug(query: str) -> str:
    """从查询猜测 feature 短名，供 locate 未命中时的 draft upsert。"""
    tokens = _LATIN_TOKEN.findall(query.casefold())
    if tokens:
        return "-".join(tokens[:5])[:80]
    compact = re.sub(r"[^\w\u4e00-\u9fff]+", "-", query.strip(), flags=re.UNICODE).strip("-")
    return (compact[:40] or "unnamed").casefold()


def _map_upsert_cli(feature: str, *, paths: Sequence[str] = (), role: str = "") -> str:
    parts = [
        "memory-hub map upsert --agent <agent>",
        f'--feature "{feature}"',
    ]
    if role:
        parts.append(f'--role "{one_line(role)}"')
    else:
        parts.append('--role "…"')
    if paths:
        for path in list(paths)[:3]:
            parts.append(f'--path "{path}"')
    else:
        parts.append('--path "…"')
    return " ".join(parts)


def _derive_map_status(
    *,
    maps_checked: int,
    missing: int = 0,
    drifted: int = 0,
    stale_tagged: int = 0,
    no_fingerprint: int = 0,
) -> str:
    """轻量对齐态：aligned | drifted | incomplete。"""
    if maps_checked < 1:
        return "incomplete"
    if missing or drifted or stale_tagged:
        return "drifted"
    if no_fingerprint:
        return "incomplete"
    return "aligned"


def _iter_project_entries(project_root: Path) -> list[Path]:
    if not project_root.is_dir():
        return []
    entries: list[Path] = []
    try:
        children = sorted(project_root.iterdir(), key=lambda item: item.name.casefold())
    except OSError:
        return []
    for child in children:
        name = child.name
        if name in PROJECT_SCAN_SKIP or name.startswith("."):
            continue
        entries.append(child)
    return entries


def _count_source_files(root: Path, *, limit: int = 400) -> int:
    count = 0
    if root.is_file():
        return 1 if root.suffix.casefold() in SOURCE_FILE_SUFFIXES else 0
    try:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in PROJECT_SCAN_SKIP or part.startswith(".") for part in path.parts):
                continue
            if path.suffix.casefold() in SOURCE_FILE_SUFFIXES:
                count += 1
                if count >= limit:
                    break
    except OSError:
        return count
    return count


def _parse_map_fields(body: str) -> dict[str, object]:
    role = ""
    authority = ""
    commands: list[str] = []
    note = ""
    paths: list[str] = []
    relations: list[str] = []
    section: str | None = None
    placeholders = {"（待补充）", "(待补充)", "（无）", "(无)"}

    def _accept(value: str) -> str | None:
        text = value.strip()
        if not text or text in placeholders:
            return None
        return text

    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- 职责："):
            role = _accept(line[len("- 职责：") :]) or ""
            section = None
            continue
        if line.startswith("- 职责:"):
            role = _accept(line[len("- 职责:") :]) or ""
            section = None
            continue
        if line.startswith("- 权威："):
            authority = _accept(line[len("- 权威：") :]) or ""
            section = None
            continue
        if line.startswith("- 权威:"):
            authority = _accept(line[len("- 权威:") :]) or ""
            section = None
            continue
        # 关联路径为规范写法；关键路径兼容历史渲染笔误
        if line in {"- 关联路径：", "- 关联路径:", "- 关键路径：", "- 关键路径:"}:
            section = "paths"
            continue
        if line in {"- 相关命令：", "- 相关命令:"}:
            section = "commands"
            continue
        if line in {"- 关系：", "- 关系:"}:
            section = "relations"
            continue
        if line.startswith("- 备注："):
            rest = line[len("- 备注：") :].strip()
            if rest:
                note = _accept(rest) or ""
                section = None
            else:
                section = "note"
            continue
        if line.startswith("- 备注:"):
            rest = line[len("- 备注:") :].strip()
            if rest:
                note = _accept(rest) or ""
                section = None
            else:
                section = "note"
            continue
        if section == "paths" and line.startswith("- "):
            accepted = _accept(line[2:])
            if accepted:
                paths.append(accepted)
        elif section == "commands" and line.startswith("- "):
            accepted = _accept(line[2:])
            if accepted:
                commands.append(accepted)
        elif section == "relations" and line.startswith("- "):
            accepted = _accept(line[2:])
            if accepted:
                relations.append(accepted)
        elif section == "note":
            fragment = line[2:].strip() if line.startswith("- ") else line
            accepted = _accept(fragment)
            if accepted:
                note = f"{note} {accepted}".strip() if note else accepted
    return {
        "role": role,
        "authority": authority,
        "paths": paths,
        "commands": commands,
        "relations": relations,
        "note": note,
    }


def _render_map_body(
    *,
    feature: str,
    role: str,
    paths: Sequence[str],
    commands: Sequence[str],
    note: str,
    agent: str,
    stamp: str,
    authority: str = "",
    links: Sequence[dict[str, str]] = (),
) -> str:
    lines = [
        f"# Feature: {feature}",
        "",
        f"- Agent: {agent}",
        f"- Updated: {stamp}",
        f"- 职责：{role or '（待补充）'}",
        f"- 权威：{authority or '（无）'}",
        "- 关联路径：",
    ]
    if paths:
        lines.extend(f"  - {path}" for path in paths)
    else:
        lines.append("  - （待补充）")
    lines.append("- 相关命令：")
    if commands:
        lines.extend(f"  - {command}" for command in commands)
    else:
        lines.append("  - （无）")
    lines.append("- 关系：")
    if links:
        for item in links:
            relation = str(item.get("relation") or "").strip()
            target = str(item.get("target") or "").strip()
            if relation and target:
                lines.append(f"  - {relation} → {target}")
    else:
        lines.append("  - （无）")
    if note:
        lines.extend(["- 备注：", f"  - {note}"])
    return "\n".join(lines).rstrip() + "\n"


class MapsMixin:
    """功能地图读写与健康检查（混入 MemoryHub）。"""

    def upsert_map(
        self,
        *,
        agent: str,
        feature: str,
        role: str = "",
        paths: Sequence[str] = (),
        commands: Sequence[str] = (),
        note: str = "",
        authority: str = "",
        source_task: str | None = None,
        confidence: str = "confirmed",
        merge_paths: bool = True,
        links: Sequence[tuple[str, str]] = (),
    ) -> dict[str, object]:
        """写入或更新功能地图（wiki + key=feature:…），供 locate 快速定位。

        FRAS 对齐：职责≈F、links≈R、authority≈A；路径漂移由 path_fingerprints 检测（S）。
        """
        self._ensure_initialized()
        agent = safe_segment(agent, "代理名")
        feature_name = _normalize_feature_name(feature)
        clean_key = normalize_memory_key(f"feature:{feature_name}")
        confidence = choice(confidence, CONFIDENCE_LEVELS, "置信度")
        clean_source_task = safe_segment(source_task, "来源任务") if source_task else ""
        clean_role = one_line(role)
        clean_note = one_line(note)
        clean_authority = one_line(authority)
        clean_commands = [one_line(item) for item in commands if str(item).strip()]
        clean_links: list[dict[str, str]] = []
        for relation, target in links:
            clean_relation = choice(relation, RELATION_TYPES, "关系类型")
            clean_target = one_line(target)
            if not clean_target:
                raise MemoryHubError("关系目标不能为空")
            clean_links.append({"relation": clean_relation, "target": clean_target})
        clean_paths: list[str] = []
        seen_paths: set[str] = set()
        for item in paths:
            normalized = _normalize_repo_path(str(item))
            folded = normalized.casefold()
            if folded in seen_paths:
                continue
            seen_paths.add(folded)
            clean_paths.append(normalized)
        if (
            not clean_role
            and not clean_paths
            and not clean_commands
            and not clean_note
            and not clean_authority
            and not clean_links
        ):
            raise MemoryHubError("地图至少需要职责、权威、路径、命令、关系或备注之一")

        stamp = now().isoformat(timespec="seconds")
        project_root = self.root.parent
        with self._write_lock():
            existing_path = self._find_by_key(clean_key)
            old_meta: dict[str, object] = {}
            old_paths: list[str] = []
            old_commands: list[str] = []
            old_links: list[dict[str, str]] = []
            old_role = ""
            old_note = ""
            old_authority = ""
            if existing_path is not None:
                try:
                    old_meta, old_body = split_frontmatter(existing_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError) as error:
                    raise MemoryHubError(f"无法读取已有地图：{error}") from error
                parsed = _parse_map_fields(old_body)
                old_role = str(parsed.get("role") or "")
                old_note = str(parsed.get("note") or "")
                old_authority = str(old_meta.get("authority") or parsed.get("authority") or "")
                meta_paths = old_meta.get("paths")
                if isinstance(meta_paths, list) and meta_paths:
                    old_paths = [str(item) for item in meta_paths]
                else:
                    old_paths = [str(item) for item in parsed.get("paths") or []]
                old_commands = [str(item) for item in parsed.get("commands") or []]
                meta_links = old_meta.get("links")
                if isinstance(meta_links, list):
                    for item in meta_links:
                        if isinstance(item, dict) and item.get("relation") and item.get("target"):
                            old_links.append(
                                {
                                    "relation": str(item["relation"]),
                                    "target": str(item["target"]),
                                }
                            )

            final_paths: list[str] = []
            seen_final: set[str] = set()

            def _append_path(raw: str) -> None:
                try:
                    normalized = _normalize_repo_path(raw)
                except MemoryHubError:
                    return
                folded = normalized.casefold()
                if folded in seen_final:
                    return
                seen_final.add(folded)
                final_paths.append(normalized)

            if merge_paths:
                for item in old_paths:
                    _append_path(item)
            for item in clean_paths:
                _append_path(item)
            if clean_commands:
                final_commands = list(dict.fromkeys(clean_commands))
            else:
                final_commands = list(dict.fromkeys(old_commands))
            final_role = clean_role or old_role
            final_note = clean_note or old_note
            final_authority = clean_authority or old_authority
            final_links = clean_links if clean_links else list(old_links)
            path_fingerprints = _path_fingerprints_for(project_root, final_paths)

            narrative = _render_map_body(
                feature=feature_name,
                role=final_role,
                paths=final_paths,
                commands=final_commands,
                note=final_note,
                agent=agent,
                stamp=stamp,
                authority=final_authority,
                links=final_links,
            )
            fingerprint = content_fingerprint(narrative)
            if existing_path is not None:
                old_hash = old_meta.get("content_hash")
                old_fps = _normalize_path_fingerprints(old_meta.get("path_fingerprints"))
                same_body = isinstance(old_hash, str) and old_hash == fingerprint
                same_fps = old_fps == path_fingerprints
                same_authority = str(old_meta.get("authority") or "") == final_authority
                same_links = old_links == final_links
                if same_body and same_fps and same_authority and same_links:
                    return {
                        **self._remember_payload(existing_path, old_meta, deduped=True),
                        "feature": feature_name,
                        "paths": final_paths,
                        "commands": final_commands,
                        "role": final_role,
                        "authority": final_authority or None,
                        "path_fingerprints": path_fingerprints,
                    }
                memory_id = str(old_meta.get("id") or f"mem-{uuid.uuid4().hex}")
                created_at = str(old_meta.get("created_at") or stamp)
                path = existing_path
                updated = True
            else:
                memory_id = f"mem-{uuid.uuid4().hex}"
                created_at = stamp
                stem = f"feature-{slug(feature_name)}"
                path = self.root / "wiki" / f"{stem}.md"
                counter = 1
                while path.exists():
                    path = self.root / "wiki" / f"{stem}-{counter}.md"
                    counter += 1
                updated = False

            metadata: dict[str, object] = {
                "id": memory_id,
                "key": clean_key,
                "feature": feature_name,
                "type": "fact",
                "source_task": clean_source_task,
                "source_agent": agent,
                "created_at": created_at,
                "updated_at": stamp,
                "confidence": confidence,
                "tags": ["map", "feature"],
                "links": final_links,
                "paths": final_paths,
                "authority": final_authority,
                "path_fingerprints": path_fingerprints,
                "stale_reason": "",
                "content_hash": fingerprint,
            }
            # 刷新地图时保留反馈计数；去掉 stale/disputed（等同已修正）
            if old_meta:
                for counter in ("feedback_useful", "feedback_stale", "feedback_wrong"):
                    if counter in old_meta:
                        metadata[counter] = int(old_meta.get(counter) or 0)
                old_tags = old_meta.get("tags")
                if isinstance(old_tags, list):
                    kept = [
                        str(tag)
                        for tag in old_tags
                        if str(tag).casefold() not in {"stale", "disputed", "map", "feature"}
                    ]
                    metadata["tags"] = ["map", "feature", *kept]
            atomic_write(path, frontmatter(metadata) + narrative)
            self._touch_index_unlocked(collections=("wiki",))
        return {
            **self._remember_payload(path, metadata, updated=updated),
            "feature": feature_name,
            "paths": final_paths,
            "commands": final_commands,
            "role": final_role,
            "authority": final_authority or None,
            "path_fingerprints": path_fingerprints,
        }

    def locate(
        self,
        query: str,
        *,
        limit: int = 5,
        min_score: int = 1,
        include_related: bool = True,
    ) -> list[dict[str, object]]:
        """按功能/路径线索定位地图，返回短结果（默认不灌全文）。优先本地倒排索引。"""
        self._ensure_initialized()
        query = query.strip()
        if not query:
            raise MemoryHubError("定位查询不能为空")
        if limit < 1:
            raise MemoryHubError("limit 必须大于 0")
        terms = tokenize_query(query)
        if not terms:
            raise MemoryHubError("定位查询不能为空")
        query_folded = query.casefold()
        docs = self._search_docs()
        hits: list[dict[str, object]] = []
        project_root = self.root.parent
        by_key: dict[str, tuple[str, dict[str, object]]] = {}

        for relative, doc in docs.items():
            if not isinstance(doc, dict):
                continue
            collection = str(doc.get("collection") or "")
            if collection not in {"wiki", "experiences", "inbox"}:
                continue
            key = str(doc.get("key") or "")
            if key:
                by_key[key.casefold()] = (relative.replace("\\", "/"), doc)
            is_map = bool(doc.get("is_map"))
            path_list = [str(item) for item in doc.get("paths") or []]
            feature = str(doc.get("feature") or Path(relative).stem)
            role = str(doc.get("role") or "")
            commands = [str(item) for item in doc.get("commands") or []]
            body_head = str(doc.get("body_head") or "")
            map_blob = "\n".join(
                [
                    body_head,
                    key.casefold(),
                    feature.casefold(),
                    role.casefold(),
                    " ".join(path_list).casefold(),
                    " ".join(commands).casefold(),
                ]
            )
            term_hits = sum(map_blob.count(term) for term in terms)
            path_hits = sum(1 for item in path_list if any(term in item.casefold() for term in terms))
            exact = 8 if query_folded in map_blob else 0
            if term_hits == 0 and path_hits == 0 and exact == 0:
                continue
            map_bonus = 18 if is_map else 0
            confidence = str(doc.get("confidence") or "unspecified")
            conf_bonus = CONFIDENCE_SCORE_ADJUST.get(confidence.casefold(), 0)
            useful = int(doc.get("feedback_useful") or 0)
            useful_bonus = min(6, useful * 2) if useful > 0 else 0
            tags = {str(tag).casefold() for tag in (doc.get("tags") or [])}
            stale_penalty = 10 if ("stale" in tags or "disputed" in tags) else 0
            penalty = (
                int(doc.get("feedback_stale") or 0) * 2
                + int(doc.get("feedback_wrong") or 0) * 4
                + stale_penalty
            )
            score = term_hits * 3 + path_hits * 6 + exact + map_bonus + conf_bonus + useful_bonus - penalty
            if score < min_score:
                continue
            fps = _normalize_path_fingerprints(doc.get("path_fingerprints"))
            inspected = _inspect_map_paths(project_root, path_list, fps)
            hits.append(
                {
                    "score": score,
                    "feature": feature,
                    "key": key or None,
                    "path": relative.replace("\\", "/"),
                    "role": role or None,
                    "authority": doc.get("authority") if isinstance(doc.get("authority"), str) else None,
                    "paths": path_list,
                    "missing_paths": inspected["missing"],
                    "drifted_paths": inspected["drifted"],
                    "commands": commands,
                    "confidence": confidence,
                    "stale_reason": doc.get("stale_reason") if isinstance(doc.get("stale_reason"), str) else None,
                    "memory_id": doc.get("id") if isinstance(doc.get("id"), str) else None,
                    "is_map": is_map,
                    "related_from": None,
                }
            )

        hits.sort(key=lambda item: (-int(item["score"]), str(item.get("key") or ""), str(item["path"])))
        primary = hits[:limit]

        if include_related and primary:
            seen_paths = {str(item.get("path") or "") for item in primary}
            related: list[dict[str, object]] = []
            for seed in primary:
                if not seed.get("is_map"):
                    continue
                seed_path = str(seed.get("path") or "")
                seed_doc = docs.get(seed_path) or docs.get(seed_path.replace("/", "\\"))
                if not isinstance(seed_doc, dict):
                    # docs keys are posix relative
                    for rel, candidate in docs.items():
                        if rel.replace("\\", "/") == seed_path and isinstance(candidate, dict):
                            seed_doc = candidate
                            break
                if not isinstance(seed_doc, dict):
                    continue
                for target in seed_doc.get("links") or []:
                    target_key = str(target).strip().casefold()
                    if not target_key:
                        continue
                    if not target_key.startswith("feature:"):
                        target_key = f"feature:{target_key}"
                    found = by_key.get(target_key)
                    if not found:
                        continue
                    rel_path, rel_doc = found
                    if rel_path in seen_paths:
                        continue
                    path_list = [str(item) for item in rel_doc.get("paths") or []]
                    fps = _normalize_path_fingerprints(rel_doc.get("path_fingerprints"))
                    inspected = _inspect_map_paths(project_root, path_list, fps)
                    related.append(
                        {
                            "score": max(RELATED_MAP_SCORE_FLOOR, int(seed["score"]) - 6),
                            "feature": str(rel_doc.get("feature") or Path(rel_path).stem),
                            "key": str(rel_doc.get("key") or "") or None,
                            "path": rel_path,
                            "role": str(rel_doc.get("role") or "") or None,
                            "authority": rel_doc.get("authority")
                            if isinstance(rel_doc.get("authority"), str)
                            else None,
                            "paths": path_list,
                            "missing_paths": inspected["missing"],
                            "drifted_paths": inspected["drifted"],
                            "commands": [str(item) for item in rel_doc.get("commands") or []],
                            "confidence": str(rel_doc.get("confidence") or "unspecified"),
                            "stale_reason": rel_doc.get("stale_reason")
                            if isinstance(rel_doc.get("stale_reason"), str)
                            else None,
                            "memory_id": rel_doc.get("id") if isinstance(rel_doc.get("id"), str) else None,
                            "is_map": True,
                            "related_from": seed.get("key") or seed.get("feature"),
                        }
                    )
                    seen_paths.add(rel_path)
            related.sort(key=lambda item: (-int(item["score"]), str(item.get("key") or ""), str(item["path"])))
            for item in related:
                if len(primary) >= limit * 2:
                    break
                primary.append(item)
        return primary

    def locate_report(
        self,
        query: str,
        *,
        limit: int = 5,
        min_score: int = 1,
    ) -> dict[str, object]:
        """locate + 命中/未命中提示 + 改动范围 scope（供 CLI/MCP；勿叠进 context 前缀）。"""
        hits = self.locate(query, limit=limit, min_score=min_score)
        draft: dict[str, object] | None = None
        if not hits:
            slug = _suggest_feature_slug(query)
            draft = {
                "feature": slug,
                "suggested_cli": _map_upsert_cli(slug),
            }
        scope_paths: list[str] = []
        seen_paths: set[str] = set()
        related_features: list[str] = []
        authorities: list[str] = []
        commands: list[str] = []
        for hit in hits:
            for path in hit.get("paths") or []:
                text = str(path).replace("\\", "/")
                if text and text not in seen_paths:
                    seen_paths.add(text)
                    scope_paths.append(text)
            feature = str(hit.get("feature") or "")
            if hit.get("related_from") and feature and feature not in related_features:
                related_features.append(feature)
            authority = str(hit.get("authority") or "").strip()
            if authority and authority not in authorities:
                authorities.append(authority)
            for cmd in hit.get("commands") or []:
                text = str(cmd).strip()
                if text and text not in commands:
                    commands.append(text)
        scope = {
            "paths": scope_paths,
            "related_features": related_features,
            "authorities": authorities,
            "commands": commands[:8],
            "gitnexus_hint": (
                "调用链 / 影响面 / 符号关系：用 GitNexus（impact / context / detect_changes）；"
                "本地图只给入口文件与 FRAS 关联，不替代符号图。"
            ),
            "change_checklist": (
                "改 scope.paths 前：读 authorities；跑 commands；改完 map upsert 刷新路径/指纹；"
                "架构波及再用 GitNexus。"
            ),
        }
        return {
            "query": query.strip(),
            "hits": hits,
            "hint": LOCATE_HIT_HINT if hits else LOCATE_MISS_HINT,
            "count": len(hits),
            "draft_upsert": draft,
            "scope": scope if hits else None,
        }

    def map_coverage(
        self,
        *,
        max_unmapped: int = 40,
        project_root: Path | str | None = None,
    ) -> dict[str, object]:
        """对照仓库顶层内容与功能地图，找出未覆盖热点（让工具知道项目还有什么）。"""
        self._ensure_initialized()
        if max_unmapped < 1:
            raise MemoryHubError("max_unmapped 必须大于 0")
        root = Path(project_root).expanduser().resolve() if project_root else Path.cwd().resolve()
        maps = self.list_maps(limit=500)
        mapped_paths: set[str] = set()
        mapped_prefixes: set[str] = set()
        for item in maps:
            for raw in item.get("paths") or []:
                rel = str(raw).strip().replace("\\", "/")
                if not rel:
                    continue
                mapped_paths.add(rel)
                mapped_prefixes.add(rel.split("/", 1)[0])
        entries = _iter_project_entries(root)
        covered: list[dict[str, object]] = []
        unmapped: list[dict[str, object]] = []
        for entry in entries:
            rel = entry.name.replace("\\", "/")
            prefix = rel
            is_covered = prefix in mapped_prefixes or any(
                path == rel or path.startswith(prefix + "/") for path in mapped_paths
            )
            source_count = _count_source_files(entry)
            row = {
                "path": rel + ("/" if entry.is_dir() else ""),
                "kind": "dir" if entry.is_dir() else "file",
                "source_files": source_count,
                "suggested_cli": _map_upsert_cli(
                    _suggest_feature_slug(rel),
                    paths=[rel],
                    role="（待补充）",
                ),
            }
            if is_covered:
                covered.append(row)
            else:
                unmapped.append(row)
        unmapped.sort(key=lambda item: (-int(item["source_files"]), str(item["path"])))
        covered.sort(key=lambda item: str(item["path"]))
        total = len(covered) + len(unmapped)
        coverage_pct = round(100.0 * len(covered) / total, 1) if total else 100.0
        return {
            "hub": str(self.root),
            "project_root": str(root),
            "maps": len(maps),
            "coverage_pct": coverage_pct,
            "covered_count": len(covered),
            "unmapped_count": len(unmapped),
            "covered": covered[:max_unmapped],
            "unmapped": unmapped[:max_unmapped],
            "hint": (
                "默认对照当前工作目录；coverage 越高新会话越少扫仓。"
                "对 unmapped 跑 map seed / map upsert。影响面用 GitNexus。"
            ),
        }

    def map_seed(
        self,
        *,
        agent: str,
        dry_run: bool = True,
        max_features: int = 40,
        min_source_files: int = 1,
        project_root: Path | str | None = None,
    ) -> dict[str, object]:
        """按仓库顶层目录/文件播种功能地图草稿（角色待补充）；默认 dry-run。"""
        self._ensure_initialized()
        agent = safe_segment(agent, "代理名")
        if max_features < 1:
            raise MemoryHubError("max_features 必须大于 0")
        coverage = self.map_coverage(max_unmapped=max_features * 2, project_root=project_root)
        planned: list[dict[str, object]] = []
        created: list[dict[str, object]] = []
        for item in coverage.get("unmapped") or []:
            if len(planned) >= max_features:
                break
            if int(item.get("source_files") or 0) < min_source_files:
                continue
            path = str(item.get("path") or "").rstrip("/")
            if not path:
                continue
            feature = _suggest_feature_slug(path)
            role = f"{path} 区域入口（seed，待补充职责）"
            plan = {
                "feature": feature,
                "path": path,
                "role": role,
                "suggested_cli": _map_upsert_cli(feature, paths=[path], role=role),
            }
            planned.append(plan)
            if not dry_run:
                created.append(
                    self.upsert_map(
                        agent=agent,
                        feature=feature,
                        role=role,
                        paths=[path],
                        confidence="inferred",
                        note="map seed 自动播种；请补 authority/links/commands",
                    )
                )
        return {
            "hub": str(self.root),
            "project_root": coverage.get("project_root"),
            "dry_run": dry_run,
            "agent": agent,
            "planned": planned,
            "created": created,
            "counts": {"planned": len(planned), "created": len(created)},
            "hint": (
                "确认后执行 memory-hub map seed --agent <agent> --apply；"
                "再补 role/authority/links，并用 locate 验证。"
            ),
        }

    def list_maps(self, *, limit: int = 100) -> list[dict[str, object]]:
        """列出功能地图（按 feature key 稳定排序）。优先 search-index，避免全量读盘。"""
        self._ensure_initialized()
        if limit < 1:
            raise MemoryHubError("limit 必须大于 0")
        items: list[dict[str, object]] = []
        project_root = self.root.parent
        for relative, doc in self._search_docs().items():
            if not isinstance(doc, dict):
                continue
            if str(doc.get("collection") or "") not in {"wiki", "experiences", "inbox"}:
                continue
            if not doc.get("is_map"):
                continue
            path_posix = str(relative).replace("\\", "/")
            key = str(doc.get("key") or "")
            path_list = [str(item) for item in (doc.get("paths") or [])]
            path_fingerprints = _normalize_path_fingerprints(doc.get("path_fingerprints"))
            inspected = _inspect_map_paths(project_root, path_list, path_fingerprints)
            edges = doc.get("link_edges")
            link_list: list[dict[str, str]] = []
            if isinstance(edges, list):
                for item in edges:
                    if isinstance(item, dict) and item.get("relation") and item.get("target"):
                        link_list.append(
                            {"relation": str(item["relation"]), "target": str(item["target"])}
                        )
            elif isinstance(doc.get("links"), list):
                for target in doc["links"]:
                    if target:
                        link_list.append({"relation": "related_to", "target": str(target)})
            items.append(
                {
                    "feature": str(doc.get("feature") or Path(path_posix).stem),
                    "key": key or None,
                    "path": path_posix,
                    "role": str(doc.get("role") or "") or None,
                    "authority": str(doc.get("authority") or "") or None,
                    "paths": path_list,
                    "path_fingerprints": path_fingerprints,
                    "missing_paths": inspected["missing"],
                    "drifted_paths": inspected["drifted"],
                    "commands": [str(item) for item in (doc.get("commands") or [])],
                    "links": link_list,
                    "confidence": str(doc.get("confidence") or "unspecified"),
                    "stale_reason": str(doc.get("stale_reason") or "") or None,
                    "memory_id": str(doc["id"]) if isinstance(doc.get("id"), str) else None,
                    "tags": [str(item) for item in (doc.get("tags") or [])],
                    "feedback_useful": int(doc.get("feedback_useful") or 0),
                    "feedback_stale": int(doc.get("feedback_stale") or 0),
                    "feedback_wrong": int(doc.get("feedback_wrong") or 0),
                }
            )
        items.sort(key=lambda item: (str(item.get("key") or "").casefold(), str(item.get("feature") or "")))
        return items[:limit]

    def map_maintain(
        self,
        *,
        paths: Sequence[str] = (),
        limit: int = 200,
    ) -> dict[str, object]:
        """变更驱动：按本次改动的仓库相对路径，签发受影响功能地图的 draft_upserts。"""
        self._ensure_initialized()
        if limit < 1:
            raise MemoryHubError("limit 必须大于 0")
        changed: list[str] = []
        seen: set[str] = set()
        for raw in paths:
            try:
                normalized = _normalize_repo_path(str(raw))
            except MemoryHubError:
                continue
            folded = normalized.casefold()
            if folded in seen:
                continue
            seen.add(folded)
            changed.append(normalized)
        if not changed:
            raise MemoryHubError("至少需要一条仓库相对路径（--path）")

        def _overlaps(map_path: str, changed_path: str) -> bool:
            left = map_path.rstrip("/")
            right = changed_path.rstrip("/")
            if not left or not right:
                return False
            return (
                left == right
                or right.startswith(left + "/")
                or left.startswith(right + "/")
            )

        maps = self.list_maps(limit=limit)
        matched: list[dict[str, object]] = []
        draft_upserts: list[dict[str, object]] = []
        for item in maps:
            map_paths = [str(rel).replace("\\", "/") for rel in (item.get("paths") or []) if rel]
            hits = [p for p in changed if any(_overlaps(mp, p) for mp in map_paths)]
            if not hits:
                continue
            role = str(item.get("role") or "")
            keep_paths = map_paths[:3] or hits[:2]
            suggested = _map_upsert_cli(
                str(item.get("feature") or "feature"),
                paths=keep_paths,
                role=role,
            )
            matched.append(
                {
                    "feature": item.get("feature"),
                    "key": item.get("key"),
                    "memory_id": item.get("memory_id"),
                    "paths": map_paths,
                    "changed_hits": hits,
                }
            )
            draft_upserts.append(
                {
                    "feature": item.get("feature"),
                    "key": item.get("key"),
                    "memory_id": item.get("memory_id"),
                    "role": role or None,
                    "paths": keep_paths,
                    "reasons": ["changed_paths"],
                    "suggested_cli": suggested,
                }
            )
        return {
            "hub": str(self.root),
            "changed_paths": changed,
            "matched_count": len(matched),
            "matched_maps": matched,
            "draft_upserts": draft_upserts,
            "hint": (
                "按 draft_upserts[].suggested_cli 刷新受影响地图；"
                "无匹配时对 changed_paths 跑 map upsert / map seed。"
            ),
        }

    def map_health(self, *, limit: int = 200) -> dict[str, object]:
        """只读检查功能地图：缺失、漂移、缺指纹、已标 stale；附 map_status / draft_upserts。"""
        self._ensure_initialized()
        if limit < 1:
            raise MemoryHubError("limit 必须大于 0")
        maps = self.list_maps(limit=limit)
        issues: list[dict[str, object]] = []
        draft_upserts: list[dict[str, object]] = []
        missing_count = 0
        drifted_count = 0
        no_fingerprint_count = 0
        stale_tagged = 0
        for item in maps:
            missing = [str(rel) for rel in (item.get("missing_paths") or [])]
            drifted = [str(rel) for rel in (item.get("drifted_paths") or [])]
            fps = item.get("path_fingerprints") or {}
            if not isinstance(fps, dict):
                fps = {}
            paths = [str(rel) for rel in (item.get("paths") or []) if rel]
            on_disk = [rel for rel in paths if rel not in missing]
            tags = {str(tag).casefold() for tag in (item.get("tags") or [])}
            needs_fp = bool(
                _file_paths_missing_fingerprint(self.root.parent, on_disk, fps)
            )
            is_stale = "stale" in tags or "disputed" in tags
            if not (missing or drifted or needs_fp or is_stale):
                continue
            if missing:
                missing_count += 1
            if drifted:
                drifted_count += 1
            if needs_fp:
                no_fingerprint_count += 1
            if is_stale:
                stale_tagged += 1
            role = str(item.get("role") or "")
            keep_paths = [p for p in paths if p not in missing][:3] or missing[:2]
            suggested = _map_upsert_cli(
                str(item.get("feature") or "feature"),
                paths=keep_paths,
                role=role,
            )
            reasons: list[str] = []
            if missing:
                reasons.append("missing")
            if drifted:
                reasons.append("drifted")
            if needs_fp:
                reasons.append("needs_fingerprint")
            if is_stale:
                reasons.append("stale")
            issues.append(
                {
                    "feature": item.get("feature"),
                    "memory_id": item.get("memory_id"),
                    "key": item.get("key"),
                    "missing_paths": missing,
                    "drifted_paths": drifted,
                    "needs_fingerprint": needs_fp,
                    "stale_tagged": is_stale,
                    "stale_reason": item.get("stale_reason"),
                    "suggested_cli": suggested,
                }
            )
            draft_upserts.append(
                {
                    "feature": item.get("feature"),
                    "key": item.get("key"),
                    "memory_id": item.get("memory_id"),
                    "role": role or None,
                    "paths": keep_paths,
                    "reasons": reasons,
                    "suggested_cli": suggested,
                }
            )
        actions: list[dict[str, str]] = []
        if missing_count or drifted_count:
            actions.append(
                {
                    "id": "evolve-apply",
                    "command": "memory-hub evolve --apply",
                    "reason": "将缺失/漂移地图标 stale",
                }
            )
        if no_fingerprint_count:
            actions.append(
                {
                    "id": "backfill-fp",
                    "command": "memory-hub migrate --backfill-map-fingerprints",
                    "reason": "批量补录路径指纹",
                }
            )
        for issue in issues[:8]:
            cli = str(issue.get("suggested_cli") or "")
            if cli:
                actions.append(
                    {
                        "id": f"repair-{issue.get('feature')}",
                        "command": cli,
                        "reason": "刷新该功能地图路径/指纹",
                    }
                )
        maps_checked = len(maps)
        map_status = _derive_map_status(
            maps_checked=maps_checked,
            missing=missing_count,
            drifted=drifted_count,
            stale_tagged=stale_tagged,
            no_fingerprint=no_fingerprint_count,
        )
        if map_status == "aligned":
            hint = "map_status=aligned；无需补写。"
        elif maps_checked < 1:
            hint = "map_status=incomplete：尚无功能地图；先 map seed / map upsert。"
        else:
            hint = (
                "map_status 未对齐：按 draft_upserts[].suggested_cli 执行 map upsert；"
                "或 evolve --apply / migrate --backfill-map-fingerprints。"
            )
        result = {
            "ok": map_status == "aligned",
            "map_status": map_status,
            "hub": str(self.root),
            "counts": {
                "maps_checked": maps_checked,
                "issues": len(issues),
                "missing": missing_count,
                "drifted": drifted_count,
                "no_fingerprint": no_fingerprint_count,
                "stale_tagged": stale_tagged,
            },
            "issues": issues,
            "draft_upserts": draft_upserts,
            "suggested_actions": actions,
            "hint": hint,
        }
        self._write_map_status_cache(result)
        return result

    def _map_status_cache_path(self) -> Path:
        return self.root / "meta" / "map-status.json"

    def _write_map_status_cache(self, health: dict[str, object]) -> None:
        try:
            (self.root / "meta").mkdir(parents=True, exist_ok=True)
            payload = {
                "map_status": health.get("map_status"),
                "ok": health.get("ok"),
                "counts": health.get("counts"),
                "issue_features": [
                    str(item.get("feature"))
                    for item in (health.get("issues") or [])[:8]
                    if item.get("feature")
                ],
                "updated_at": now().isoformat(timespec="seconds"),
            }
            atomic_write(
                self._map_status_cache_path(),
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            )
        except OSError:
            pass

    def read_map_status_cache(self) -> dict[str, object] | None:
        """轻量读取上次 map_health/sync 写入的对齐态（无扫盘）。"""
        path = self._map_status_cache_path()
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None
