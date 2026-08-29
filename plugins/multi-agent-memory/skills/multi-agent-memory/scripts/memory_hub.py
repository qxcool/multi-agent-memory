#!/usr/bin/env python3
"""Skill-local CLI entry. Prefer `memory-hub` on PATH when the package is installed."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_package() -> None:
    try:
        import multi_agent_memory  # noqa: F401

        return
    except ImportError:
        pass

    here = Path(__file__).resolve()
    for parent in here.parents:
        src = parent / "src"
        if (src / "multi_agent_memory").is_dir():
            sys.path.insert(0, str(src))
            return
        local = parent / "multi_agent_memory"
        if local.is_dir() and (local / "__init__.py").is_file():
            sys.path.insert(0, str(parent))
            return

    sys.stderr.write(
        "错误：找不到 multi_agent_memory 包。\n"
        "请先安装：python -m pip install <plugin-root>\n"
        "或从完整仓库运行，使 scripts 能解析到 src/multi_agent_memory。\n"
    )
    raise SystemExit(1)


_ensure_package()

from multi_agent_memory.cli import main  # noqa: E402


if __name__ == "__main__":
    main()
