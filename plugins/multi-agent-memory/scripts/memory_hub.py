#!/usr/bin/env python3
"""兼容入口：委托给 Skill 旁脚本，保持旧文档路径可用。"""

from __future__ import annotations

import runpy
from pathlib import Path


SKILL_ENTRY = Path(__file__).resolve().parents[1] / "skills" / "multi-agent-memory" / "scripts" / "memory_hub.py"

if __name__ == "__main__":
    runpy.run_path(str(SKILL_ENTRY), run_name="__main__")
