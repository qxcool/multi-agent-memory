#!/usr/bin/env python3
"""Cursor stop：可选自动跟进 close/evolve（默认关闭，避免打扰）。"""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}
    status = str(payload.get("status") or "")
    loop_count = int(payload.get("loop_count") or 0)
    enabled = os.environ.get("MEMORY_HUB_STOP_FOLLOWUP", "").strip() in {"1", "true", "yes"}
    out: dict[str, str] = {}
    if enabled and status == "completed" and loop_count == 0 and os.environ.get("MEMORY_HUB_ROOT"):
        out["followup_message"] = (
            "若本会话完成了有价值改动，请运行："
            "`memory-hub close --task <task> --agent <agent>`，"
            "或 `memory-hub evolve` 查看自我进化建议。若无需收尾可忽略。"
        )
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
