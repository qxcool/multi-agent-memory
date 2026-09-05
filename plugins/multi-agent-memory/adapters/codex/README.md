# Codex 适配

本插件已通过 `.codex-plugin/plugin.json` 安装 Skill。Codex 侧优先依赖 Skill description 触发 + CLI。

## 建议节奏

1. 开场：`memory-hub orient --task … --agent codex --query "…"`
2. 定位：`memory-hub locate --query "…"`
3. 收尾：`memory-hub close --task … --agent codex`

## MCP（可选）

若宿主支持 MCP stdio：

```text
command: memory-hub-mcp
```

或 `python -m multi_agent_memory.mcp_server`。
