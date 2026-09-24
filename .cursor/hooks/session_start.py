#!/usr/bin/env python3
"""Cursor sessionStart：注入开场提醒（短前缀），并设置会话环境变量。"""

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
        "未命中：map upsert 补地图；架构溯源用 GitNexus，不要用全仓文本扫代替。",
        "收尾：memory-hub close --task <task> --agent cursor（可选 --lesson / --archive / --evolve-maps）。",
    ]
    if hub is None:
        context_lines.append(
            "未见记忆库：设置 MEMORY_HUB_ROOT，或 memory-hub init，或 --hub <path>。"
        )
    else:
        context_lines.append(f"已发现记忆库：{hub}")

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
