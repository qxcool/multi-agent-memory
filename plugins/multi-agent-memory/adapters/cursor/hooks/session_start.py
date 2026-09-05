#!/usr/bin/env python3
"""Cursor sessionStart：注入开场提醒（短前缀），并设置会话环境变量。"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}
    cwd = Path.cwd()
    hub = None
    current = cwd
    while True:
        candidate = current / ".ai-memory-hub"
        if candidate.is_dir():
            hub = candidate
            break
        if current.parent == current:
            break
        current = current.parent

    context_lines = [
        "[multi-agent-memory]",
        "开场优先：memory-hub orient --task <task> --agent <agent> --query \"<固定检索词>\" --objective \"…\"",
        "将返回的 context 整段注入一次；勿叠 locate+context 双前缀。",
        "收尾：memory-hub close --task <task> --agent <agent>（可选 --lesson / --archive）。",
        "定位功能：memory-hub locate --query \"…\"；写地图：map upsert。",
    ]
    if hub is None:
        context_lines.append("当前工作区未见 .ai-memory-hub；需要时先 memory-hub init。")
    else:
        context_lines.append(f"已发现记忆库：{hub}")

    out = {
        "env": {
            "MEMORY_HUB_ROOT": str(hub) if hub else "",
            "MEMORY_HUB_SKILL": "1",
        },
        "additional_context": "\n".join(context_lines),
    }
    # session_id 可用于调试，不强制写入
    _ = payload.get("session_id")
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
