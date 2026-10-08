#!/usr/bin/env python3
"""Cursor stop：默认跟进 sync/close；MEMORY_HUB_STOP_FOLLOWUP=0 关闭。"""

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
    # 默认开启；显式 0/false/no/off 关闭
    flag = os.environ.get("MEMORY_HUB_STOP_FOLLOWUP", "1").strip().casefold()
    enabled = flag not in {"0", "false", "no", "off"}
    out: dict[str, str] = {}
    if enabled and status == "completed" and loop_count == 0:
        out["followup_message"] = (
            "若本会话有代码/记忆相关改动，请先："
            "`memory-hub sync`（或 `close --task <task> --agent cursor`）；"
            "若 maintenance_required / map_status≠aligned，"
            "必须按 draft_upserts 执行 map upsert，未对齐前勿视为收尾完成。"
            "语义补写靠 Agent；GitNexus/AOCI 不捆绑。关闭跟进：MEMORY_HUB_STOP_FOLLOWUP=0。"
        )
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
