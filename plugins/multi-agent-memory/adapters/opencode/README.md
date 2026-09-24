# OpenCode 适配

OpenCode 通常从以下位置发现技能（与 DeepSeek 有重叠）：

- `<workspace>/.opencode/skills`
- `~/.agents/skills`（推荐共享）
- 其它宿主兼容目录（视版本而定）

## Skill

```text
~/.agents/skills/multi-agent-memory  →  <plugin>/skills/multi-agent-memory
# 或
~/.opencode/skills/multi-agent-memory → 同上
# 或项目级
<workspace>/.opencode/skills/multi-agent-memory
```

```powershell
# Windows
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts opencode
```

```bash
# macOS / Linux
./plugins/multi-agent-memory/scripts/install.sh --hosts opencode
```

## `--agent`

稳定短名：`opencode`。

## MCP（可选）

配置文件常见位置：

| OS | 用户级（约） |
|---|---|
| Windows | `%APPDATA%\opencode\opencode.jsonc` |
| macOS / Linux | `~/.config/opencode/opencode.jsonc` |

也可写项目级 `opencode.jsonc`。示例见 [opencode.jsonc.example](opencode.jsonc.example)：

```jsonc
{
  "mcp": {
    "multi-agent-memory": {
      "type": "local",
      "command": ["memory-hub-mcp"],
      "enabled": true
    }
  }
}
```

入口不在 PATH 时：`"command": ["python3", "-m", "multi_agent_memory.mcp_server"]`（Windows 可改 `python`）。

## 节奏与定位纪律

见 [../shared-workflow.md](../shared-workflow.md)。摘要：

```bash
memory-hub orient --task <task> --agent opencode --query "…" --objective "…"
memory-hub locate --query "…"
memory-hub close --task <task> --agent opencode
```
