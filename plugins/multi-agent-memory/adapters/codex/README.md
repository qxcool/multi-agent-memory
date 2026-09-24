# Codex 适配

本插件根目录的 `.codex-plugin/plugin.json` 声明 Skill 路径 `./skills/`。Codex 通过 marketplace 安装，无需再拷一份 Skill。

## 安装

```powershell
# Windows（或任意已装 Codex CLI 的 shell）
codex plugin marketplace add qxcool/multi-agent-memory
codex plugin add multi-agent-memory@multi-agent-memory
python -m pip install ./plugins/multi-agent-memory
```

```bash
# macOS / Linux
codex plugin marketplace add qxcool/multi-agent-memory
codex plugin add multi-agent-memory@multi-agent-memory
python3 -m pip install ./plugins/multi-agent-memory
```

升级后若缓存仍停在旧版本，重新 `plugin add` / 刷新 marketplace，或删除：

```text
~/.codex/plugins/cache/multi-agent-memory/multi-agent-memory/<旧版本>/
```

安装脚本遇到 `codex` 只会提示 marketplace，不会创建 Skill 链接：

```powershell
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts codex -SkipPip
```

```bash
./plugins/multi-agent-memory/scripts/install.sh --hosts codex --skip-pip
```

## `--agent`

稳定短名：`codex`。

## 节奏与定位纪律

见 [../shared-workflow.md](../shared-workflow.md)。摘要：

1. 开场：`memory-hub orient --task … --agent codex --query "…"`
2. 定位：`memory-hub locate --query "…"`（命中则勿全仓 rg）
3. 收尾：`memory-hub close --task … --agent codex`

## MCP（可选）

若 Codex / 宿主支持 MCP stdio：见 [mcp.json.example](mcp.json.example)（推荐 `python -m multi_agent_memory.mcp_server`）。  
工具说明：[../../skills/multi-agent-memory/references/mcp-tools.md](../../skills/multi-agent-memory/references/mcp-tools.md)。
