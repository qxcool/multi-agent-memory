# Codex 适配

本插件根目录的 `.codex-plugin/plugin.json` 声明 Skill 路径 `./skills/`。Codex 通过 marketplace 安装，无需再拷一份 Skill。

## 安装

```powershell
codex plugin marketplace add qxcool/multi-agent-memory
codex plugin add multi-agent-memory@multi-agent-memory
```

升级后若缓存仍停在旧版本，重新 `plugin add` / 刷新 marketplace，或删除：

```text
~/.codex/plugins/cache/multi-agent-memory/multi-agent-memory/<旧版本>/
```

仍需本机 CLI：

```bash
python -m pip install ./plugins/multi-agent-memory
```

## 节奏

1. 开场：`memory-hub orient --task … --agent codex --query "…"`
2. 定位：`memory-hub locate --query "…"`
3. 收尾：`memory-hub close --task … --agent codex`

## MCP（可选）

若 Codex / 宿主支持 MCP stdio：`memory-hub-mcp` 或 `python -m multi_agent_memory.mcp_server`。
