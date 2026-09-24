# Claude Code 适配

## Skill

将插件内 Skill 链接到用户 Skill 目录（推荐 junction/symlink，勿复制分叉）：

```text
~/.claude/skills/multi-agent-memory  →  <plugin>/skills/multi-agent-memory
```

```powershell
# Windows
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts claude
```

```bash
# macOS / Linux
./plugins/multi-agent-memory/scripts/install.sh --hosts claude
```

## `--agent`

稳定短名：`claude`。

## 节奏与定位纪律

见 [../shared-workflow.md](../shared-workflow.md)。摘要：

```bash
memory-hub orient --task <task> --agent claude --query "<固定检索词>" --objective "…"
memory-hub locate --query "…"          # 命中则勿全仓 rg
memory-hub close --task <task> --agent claude
```

## MCP（可选）

```bash
# 推荐（PATH 常无 Scripts）
claude mcp add multi-agent-memory -- python -m multi_agent_memory.mcp_server
# 或
claude mcp add multi-agent-memory -- memory-hub-mcp
```

或写入用户/项目 MCP 配置，示例见 [mcp.json.example](mcp.json.example)。  
工具说明：[../../skills/multi-agent-memory/references/mcp-tools.md](../../skills/multi-agent-memory/references/mcp-tools.md)。

## 说明

- Claude 通过 `SKILL.md` 的 `description` 触发；写操作走 `memory-hub`（写锁）。
- 若使用 CC Switch 同步技能，请保证最终指向本插件的 `skills/multi-agent-memory`，避免旧 checkout 分叉。
