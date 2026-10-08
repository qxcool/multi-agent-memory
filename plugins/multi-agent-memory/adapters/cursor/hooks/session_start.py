#!/usr/bin/env python3
"""Cursor sessionStart：注入开场提醒；优先读 map-status 缓存（不扫盘）。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _discover_hub(cwd: Path) -> Path | None:
    env_hub = os.environ.get("MEMORY_HUB_ROOT", "").strip()
    if env_hub:
        path = Path(env_hub).expanduser()
        if path.is_dir():
            return path.resolve()
    current = cwd.resolve()
    while True:
        candidate = current / ".ai-memory-hub"
        if candidate.is_dir():
            return candidate.resolve()
        if current.parent == current:
            break
        current = current.parent
    return None


def _map_status_line(hub: Path) -> str | None:
    """只读 meta/map-status.json；缺失则提示 sync --check，绝不跑 list_maps。"""
    cache = hub / "meta" / "map-status.json"
    if not cache.is_file():
        return "尚无 map-status 缓存；有空跑 memory-hub sync --check。"
    try:
        data = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "map-status 缓存不可读；请 memory-hub sync --check。"
    if not isinstance(data, dict):
        return None
    status = str(data.get("map_status") or "unknown")
    if status == "aligned":
        return "map_status=aligned（缓存）。"
    features = data.get("issue_features") or []
    sample = "、".join(str(item) for item in features[:3] if item)
    extra = f"：{sample}" if sample else ""
    return (
        f"map_status={status}{extra}；请 memory-hub sync 后按 draft_upserts 补地图。"
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}
    hub = _discover_hub(Path.cwd())

    context_lines = [
        "[multi-agent-memory]",
        "开场优先：memory-hub orient --task <task> --agent cursor --query \"<固定检索词>\" --objective \"…\"",
        "将返回的 context 整段注入一次；勿叠 locate+context 双前缀。",
        "定位：先 memory-hub locate --query \"…\"；命中则打开 paths，禁止全仓 rg/Glob。",
        "变动后：memory-hub sync（机械：evolve+reindex）；语义 map upsert 仍靠 Agent。",
        "收尾：memory-hub close --task <task> --agent cursor（默认含 sync）。",
        "分工：MAM=功能/教训/交接；GitNexus=符号图；AOCI=可选全量认知（均不捆绑）。",
    ]
    if hub is None:
        context_lines.append(
            "未见记忆库：设置 MEMORY_HUB_ROOT，或 memory-hub init，或 --hub <path>。"
        )
    else:
        context_lines.append(f"已发现记忆库：{hub}")
        status_line = _map_status_line(hub)
        if status_line:
            context_lines.append(status_line)

    out = {
        "env": {
            "MEMORY_HUB_ROOT": str(hub) if hub else os.environ.get("MEMORY_HUB_ROOT", ""),
            "MEMORY_HUB_SKILL": "1",
        },
        "additional_context": "\n".join(context_lines),
    }
    _ = payload.get("session_id")
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
