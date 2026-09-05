# Cursor 适配

## Skill

```text
~/.cursor/skills/multi-agent-memory  →  <plugin>/skills/multi-agent-memory
```

```powershell
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts cursor
```

项目级也可放在 `<repo>/.cursor/skills/multi-agent-memory`。

## Hooks（项目级）

在仓库根目录：

```powershell
New-Item -ItemType Directory -Force .cursor\hooks | Out-Null
Copy-Item plugins\multi-agent-memory\adapters\cursor\hooks\*.py .cursor\hooks\
Copy-Item plugins\multi-agent-memory\adapters\cursor\hooks.json .cursor\hooks.json
```

或编辑 `.cursor/hooks.json`：

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      { "command": "python .cursor/hooks/session_start.py", "timeout": 10 }
    ],
    "stop": [
      { "command": "python .cursor/hooks/stop.py", "timeout": 5, "loop_limit": 1 }
    ]
  }
}
```

行为：

- `sessionStart`：短提醒 + `MEMORY_HUB_ROOT` / `MEMORY_HUB_SKILL`
- `stop`：默认不跟进；`MEMORY_HUB_STOP_FOLLOWUP=1` 时提示 close/evolve（`loop_limit: 1`）

> 部分 Cursor 版本对 `sessionStart.additional_context` 有竞态；完整上下文请用 `memory-hub orient`。

## MCP（可选）

合并用户或项目 MCP 配置，示例见 [mcp.json.example](mcp.json.example)：

```json
{
  "mcpServers": {
    "multi-agent-memory": {
      "command": "memory-hub-mcp",
      "args": []
    }
  }
}
```

## 节奏

```bash
memory-hub orient --task <task> --agent cursor --query "…" --objective "…"
memory-hub close --task <task> --agent cursor
```
