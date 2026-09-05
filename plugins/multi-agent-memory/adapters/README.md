# 宿主适配总览

Skill 正文只有一份：`../skills/multi-agent-memory/`（`SKILL.md`）。  
各宿主差异只在**安装路径**与**可选 sidecar**（hooks / MCP / plugin 清单）。

## 支持矩阵

| 宿主 | Skill 安装位置 | 额外适配 | `--agent` 建议短名 |
|---|---|---|---|
| Claude Code | `~/.claude/skills/multi-agent-memory` | [claude/](claude/) | `claude` |
| Codex | `.codex-plugin` + marketplace | [codex/](codex/) | `codex` |
| Cursor | `~/.cursor/skills/…` 或项目 `.cursor/skills` | [cursor/](cursor/) hooks + MCP | `cursor` |
| DeepSeek Harness | 优先 `~/.agents/skills/…`（亦扫 `.claude`/`.cursor`/`.opencode`） | [deepseek-harness/](deepseek-harness/) | `deepseek` |
| OpenCode | `~/.agents/skills/…` 或 `~/.opencode/skills` / 项目 `.opencode/skills` | [opencode/](opencode/) MCP 示例 | `opencode` |
| 其它兼容 Agent Skills 的宿主 | 拷到其 skills 目录 | 通常无需额外文件 | 自定短名 |

CLI / MCP 对所有宿主相同（装一次即可）：

```bash
python -m pip install ./plugins/multi-agent-memory
memory-hub doctor
memory-hub-mcp   # 可选
```

一键安装（Skill 链接到多宿主 + pip）：

```powershell
# Windows
.\plugins\multi-agent-memory\scripts\install.ps1
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts claude,cursor,deepseek,opencode
```

```bash
# macOS / Linux
./plugins/multi-agent-memory/scripts/install.sh
./plugins/multi-agent-memory/scripts/install.sh --hosts claude,cursor,deepseek,opencode
```

## 设计原则

1. **一份 Skill**：禁止在 adapters 里复制 SKILL.md 正文。  
2. **链接优于拷贝**：安装脚本默认创建 junction（Windows）或 symlink（Unix）指向插件内 skill。  
3. **`--agent` 稳定短名**：写入 sessions 文件名，跨宿主协作时不要改来改去。  
4. **hooks / MCP 可选**：不强制；Cursor hooks 默认只提醒，不自动灌全文（护前缀缓存）。

## 验证

```bash
memory-hub --version 2>/dev/null || python -c "import multi_agent_memory as m; print(m.__version__)"
memory-hub doctor
# 各宿主能看到 Skill「multi-agent-memory」即可
```
