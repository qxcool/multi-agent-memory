"""伴生工具探测（GitNexus / AOCI）：只检测，永不安装。"""

from __future__ import annotations

import shutil
from pathlib import Path


def mcp_config_mentions(project_root: Path, needle: str) -> bool:
    """只读扫描常见 MCP 配置是否提及伴生工具名（不解析完整 schema）。"""
    needle_cf = needle.casefold()
    candidates = [
        project_root / ".cursor" / "mcp.json",
        project_root / ".mcp.json",
        project_root / "opencode.json",
        project_root / ".opencode.json",
        Path.home() / ".cursor" / "mcp.json",
    ]
    for path in candidates:
        try:
            if path.is_file() and needle_cf in path.read_text(encoding="utf-8", errors="ignore").casefold():
                return True
        except OSError:
            continue
    return False


def probe_companions(*, project_root: Path | str | None = None) -> dict[str, object]:
    """探测 GitNexus / AOCI（只检测，永不安装）。"""
    root = Path(project_root).expanduser().resolve() if project_root else Path.cwd().resolve()
    gitnexus_cli = shutil.which("gitnexus")
    gitnexus_mcp = mcp_config_mentions(root, "gitnexus")
    gitnexus_status = "available" if gitnexus_cli or gitnexus_mcp else "missing"
    aoci_cli = shutil.which("aoci") or shutil.which("aoci.exe")
    aoci_index = (root / "aoci.txt").is_file()
    aoci_status = "available" if aoci_cli or aoci_index else "missing"
    return {
        "gitnexus": {
            "status": gitnexus_status,
            "cli": gitnexus_cli,
            "mcp_configured": gitnexus_mcp,
            "role": "符号关系、调用链、影响面",
            "install_hint": (
                "自行安装/配置 GitNexus MCP 或 CLI；本插件不捆绑。"
                "用途：架构溯源，不替代功能地图。"
            ),
        },
        "aoci": {
            "status": aoci_status,
            "cli": aoci_cli,
            "index_present": aoci_index,
            "role": "可选：仓库级逐文件/表认知索引（Whole-Index）",
            "install_hint": (
                "自行安装 AOCI-CODE（https://github.com/aoci-spec/aoci-code）；本插件不捆绑。"
                "用途：全量文件认知，不替代 orient/close/教训层。"
            ),
        },
        "hint": "伴生工具只探测不安装；缺失不影响本插件核心功能。",
    }
