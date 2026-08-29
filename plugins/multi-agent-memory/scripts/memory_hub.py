#!/usr/bin/env python3
"""无需安装即可运行的兼容入口。"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from multi_agent_memory.cli import main  # noqa: E402


if __name__ == "__main__":
    main()
