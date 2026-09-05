"""本地倒排侧车：Markdown 仍是真相源，索引加速 recall/locate。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

SEARCH_INDEX_VERSION = 1
SEARCH_INDEX_RELATIVE = "meta/search-index.json"


def search_index_path(root: Path) -> Path:
    return root / SEARCH_INDEX_RELATIVE


def empty_index() -> dict[str, Any]:
    return {"version": SEARCH_INDEX_VERSION, "built_at": "", "docs": {}}


def load_index(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return empty_index()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return empty_index()
    if not isinstance(payload, dict) or not isinstance(payload.get("docs"), dict):
        return empty_index()
    payload.setdefault("version", SEARCH_INDEX_VERSION)
    payload.setdefault("built_at", "")
    return payload


def save_index(path: Path, payload: dict[str, Any], *, atomic_write: Callable[[Path, str], None]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def term_counts(tokens: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for term in tokens:
        if not term:
            continue
        counts[term] = counts.get(term, 0) + 1
    return counts


def build_doc(
    *,
    relative: str,
    metadata: dict[str, object],
    body: str,
    tokenize: Callable[[str], list[str]],
    parse_map_fields: Callable[[str], dict[str, object]],
) -> dict[str, Any]:
    tags = metadata.get("tags", [])
    tag_list = [str(item) for item in tags] if isinstance(tags, list) else [str(tags)] if tags else []
    key = metadata.get("key") if isinstance(metadata.get("key"), str) else ""
    feature = metadata.get("feature") if isinstance(metadata.get("feature"), str) else ""
    record_type = metadata.get("type") if isinstance(metadata.get("type"), str) else "legacy"
    confidence = metadata.get("confidence") if isinstance(metadata.get("confidence"), str) else "unspecified"
    memory_id = metadata.get("id") if isinstance(metadata.get("id"), str) else None
    meta_paths = metadata.get("paths")
    path_list = [str(item) for item in meta_paths] if isinstance(meta_paths, list) else []
    tag_folded = {item.casefold() for item in tag_list}
    is_map = bool(key and key.casefold().startswith("feature:")) or "map" in tag_folded or "feature" in tag_folded
    parsed = (
        parse_map_fields(body)
        if is_map or path_list
        else {"role": "", "paths": [], "commands": [], "note": ""}
    )
    if not path_list:
        path_list = [str(item) for item in parsed.get("paths") or []]
    if not feature:
        feature = key.split(":", 1)[1] if key.casefold().startswith("feature:") else Path(relative).stem

    lines = [line.strip() for line in body.splitlines() if line.strip()]
    title = next((line.lstrip("# ") for line in lines if line.startswith("#")), Path(relative).stem)
    body_terms = term_counts(tokenize(body))
    title_terms = list(dict.fromkeys(tokenize(title)))
    tag_terms = list(dict.fromkeys(tokenize(" ".join(tag_list))))
    path_terms = list(dict.fromkeys(tokenize(relative + " " + " ".join(path_list))))
    role = str(parsed.get("role") or "")
    commands = [str(item) for item in parsed.get("commands") or []]
    map_blob = " ".join([key, feature, role, " ".join(path_list), " ".join(commands)])
    map_terms = term_counts(tokenize(map_blob)) if (is_map or path_list) else {}

    useful = metadata.get("feedback_useful")
    stale = metadata.get("feedback_stale")
    wrong = metadata.get("feedback_wrong")
    links = metadata.get("links")
    link_targets: list[str] = []
    if isinstance(links, list):
        for item in links:
            if isinstance(item, dict) and item.get("target"):
                link_targets.append(str(item.get("target")))
    return {
        "path": relative,
        "id": memory_id,
        "type": record_type,
        "confidence": confidence,
        "tags": tag_list,
        "key": key or None,
        "feature": feature,
        "title": title,
        "is_map": is_map,
        "paths": path_list,
        "role": role or None,
        "commands": commands,
        "source_task": metadata.get("source_task") if isinstance(metadata.get("source_task"), str) else None,
        "source_agent": metadata.get("source_agent") if isinstance(metadata.get("source_agent"), str) else None,
        "created_at": metadata.get("created_at") if isinstance(metadata.get("created_at"), str) else None,
        "links": link_targets,
        "feedback_useful": int(useful) if isinstance(useful, int) else 0,
        "feedback_stale": int(stale) if isinstance(stale, int) else 0,
        "feedback_wrong": int(wrong) if isinstance(wrong, int) else 0,
        "body_terms": body_terms,
        "title_terms": title_terms,
        "tag_terms": tag_terms,
        "path_terms": path_terms,
        "map_terms": map_terms,
        "body_head": body.casefold()[:4000],
        "collection": relative.split("/", 1)[0] if "/" in relative else relative.split("\\", 1)[0],
    }


def candidate_paths_for_terms(docs: dict[str, Any], terms: Sequence[str]) -> set[str]:
    if not terms:
        return set()
    hits: set[str] = set()
    for relative, doc in docs.items():
        if not isinstance(doc, dict):
            continue
        body_terms = doc.get("body_terms") if isinstance(doc.get("body_terms"), dict) else {}
        title_terms = {str(item) for item in doc.get("title_terms") or []}
        tag_terms = {str(item) for item in doc.get("tag_terms") or []}
        path_terms = {str(item) for item in doc.get("path_terms") or []}
        map_terms = doc.get("map_terms") if isinstance(doc.get("map_terms"), dict) else {}
        body_head = str(doc.get("body_head") or "")
        title = str(doc.get("title") or "").casefold()
        tags_text = " ".join(str(item) for item in doc.get("tags") or []).casefold()
        path_text = relative.casefold()
        for term in terms:
            if (
                term in body_terms
                or term in title_terms
                or term in tag_terms
                or term in path_terms
                or term in map_terms
                or term in body_head
                or term in title
                or term in tags_text
                or term in path_text
            ):
                hits.add(relative)
                break
    return hits
