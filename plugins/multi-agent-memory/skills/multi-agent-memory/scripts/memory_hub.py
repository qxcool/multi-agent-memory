#!/usr/bin/env python3
"""Skill-local CLI entry. Prefer `memory-hub` on PATH when the package is installed."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_package() -> None:
    here = Path(__file__).resolve()
    # Layout A: <plugin>/skills/<name>/scripts/this.py → parents[3] = <plugin>
    # Layout B: <plugin>/scripts/this.py → parents[1] = <plugin>
    for root in (here.parents[3], here.parents[1]):
        src = root / "src"
        if (src / "multi_agent_memory").is_dir():
            sys.path.insert(0, str(src))
            return


_ensure_package()

from multi_agent_memory.cli import main  # noqa: E402


if __name__ == "__main__":
    main()
