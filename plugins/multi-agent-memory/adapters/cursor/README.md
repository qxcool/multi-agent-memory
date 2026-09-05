# Cursor 适配

将 hooks 接到项目或用户级 Cursor hooks。

## 安装（项目级）

在仓库根目录：

```powershell
New-Item -ItemType Directory -Force .cursor\hooks | Out-Null
Copy-Item plugins\multi-agent-memory\adapters\cursor\hooks\*.py .cursor\hooks\
```

`.cursor/hooks.json`：

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

## 行为

- `sessionStart`：注入短提醒（orient/close/locate），并设置 `MEMORY_HUB_ROOT` / `MEMORY_HUB_SKILL`
- `stop`：默认**不**自动跟进；设置环境变量 `MEMORY_HUB_STOP_FOLLOWUP=1` 后，在完成时跟进一条 close/evolve 提示（`loop_limit: 1`）

> 注：部分 Cursor 版本对 `sessionStart.additional_context` 存在竞态；短提醒仍有助于 Skill 触发，完整上下文请用 `memory-hub orient`。

## MCP（可选）

Cursor MCP 配置示例：

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

或：

```json
{
  "mcpServers": {
    "multi-agent-memory": {
      "command": "python",
      "args": ["-m", "multi_agent_memory.mcp_server"]
    }
  }
}
```
