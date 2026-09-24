# 宿主适配总览

Skill 正文只有一份：`../skills/multi-agent-memory/`（`SKILL.md`）。  
各宿主差异只在**安装路径**与**可选 sidecar**（hooks / MCP / plugin 清单）。

**共用节奏与「先 locate、勿全仓 rg」纪律**：[shared-workflow.md](shared-workflow.md)  
**Windows / macOS / Linux 混用**：[cross-platform.md](cross-platform.md)

## 支持矩阵

| 宿主 | Skill 安装位置 | 额外适配 | `--agent` |
|---|---|---|---|
| Claude Code | `~/.claude/skills/multi-agent-memory` | [claude/](claude/) | `claude` |
| Codex | `.codex-plugin` + marketplace | [codex/](codex/) | `codex` |
| Cursor | `~/.cursor/skills/…` 或项目 `.cursor/skills` | [cursor/](cursor/) hooks + MCP | `cursor` |
| DeepSeek Harness | 优先 `~/.agents/skills/…` | [deepseek-harness/](deepseek-harness/) | `deepseek` |
| OpenCode | `~/.agents/skills` 或 `~/.opencode/skills` | [opencode/](opencode/) MCP | `opencode` |
| Qoder | `~/.qoder/skills/…` 或项目 `.qoder/skills` | [qoder/](qoder/) MCP | `qoder` |

CLI / MCP 对所有宿主相同（装一次即可）：

```bash
python -m pip install ./plugins/multi-agent-memory
memory-hub doctor
python -m multi_agent_memory.mcp_server   # 可选；或 memory-hub-mcp
```

MCP 工具说明（15 个）：[skills/.../references/mcp-tools.md](../skills/multi-agent-memory/references/mcp-tools.md)。  
配置推荐 `python -m multi_agent_memory.mcp_server`（见 [mcp.stdio.example.json](mcp.stdio.example.json)）。

一键安装（Skill 链接到多宿主 + pip）：

```powershell
# Windows — 默认含 claude/cursor/deepseek/opencode/qoder
.\plugins\multi-agent-memory\scripts\install.ps1
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts claude,cursor,deepseek,opencode,qoder,codex
```

```bash
# macOS / Linux
./plugins/multi-agent-memory/scripts/install.sh
./plugins/multi-agent-memory/scripts/install.sh --hosts claude,cursor,deepseek,opencode,qoder
```

Codex 需 marketplace（脚本会提示，不替代 `codex plugin add`）。

## 设计原则

1. **不限制环境**：Win / macOS / Linux + 六宿主同一套 Skill / CLI / hub；见 [cross-platform.md](cross-platform.md)。  
2. **一份 Skill**：禁止在 adapters 里复制 SKILL.md 正文。  
3. **链接优于拷贝**：安装脚本默认创建 junction（Windows）或 symlink（Unix）。  
4. **`--agent` 稳定短名**：写入 sessions 文件名；跨宿主/跨机交接同一 task 时不要改短名。  
5. **hooks / MCP 可选**：默认只提醒、不自动灌全文（护前缀缓存）。  
6. **地图优先于全仓检索**：见 shared-workflow；路径只用仓库相对路径（正斜杠）。

## 验证

```bash
memory-hub --version 2>/dev/null || python -c "import multi_agent_memory as m; print(m.__version__)"
memory-hub doctor
# 各宿主能看到 Skill「multi-agent-memory」即可（Qoder 可 /skills reload）
```
