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
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts opencode
```

## MCP（可选）

合并进 `%APPDATA%/opencode/opencode.jsonc`（或项目配置），参见 [opencode.jsonc.example](opencode.jsonc.example)：

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

## 节奏

```bash
memory-hub orient --task <task> --agent opencode --query "…" --objective "…"
memory-hub close --task <task> --agent opencode
```
