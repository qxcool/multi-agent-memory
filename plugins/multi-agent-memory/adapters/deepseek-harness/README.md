# DeepSeek Harness 适配

DeepSeek Harness 按约定发现 Agent Skills（大致优先级）：

1. `<workspace>/.agents/skills`
2. `<workspace>/skills`
3. `<workspace>/.opencode/skills`
4. `<workspace>/.claude/skills`
5. `<workspace>/.cursor/skills`
6. `~/.agents/skills`
7. `~/.claude/skills`
8. `~/.deepseek/skills`

## 推荐安装

优先装到共享目录（Claude / OpenCode / DeepSeek 都能扫到）：

```text
~/.agents/skills/multi-agent-memory  →  <plugin>/skills/multi-agent-memory
```

```powershell
# Windows
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts deepseek
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts deepseek -ProjectAgents -SkipPip
```

```bash
# macOS / Linux
./plugins/multi-agent-memory/scripts/install.sh --hosts deepseek
./plugins/multi-agent-memory/scripts/install.sh --hosts deepseek --project-agents --skip-pip
```

也可在项目内：

```text
<workspace>/.agents/skills/multi-agent-memory  →  同上
```

## `--agent`

稳定短名：`deepseek`（跨宿主交接同一 task 时勿改）。

## 节奏与定位纪律

见 [../shared-workflow.md](../shared-workflow.md)。摘要：

```bash
memory-hub orient --task <task> --agent deepseek --query "…" --objective "…"
memory-hub locate --query "…"
memory-hub close --task <task> --agent deepseek
```

## 其它入口

- Harness：`/skill install github:qxcool/multi-agent-memory`（若宿主支持 GitHub 技能安装，装完后仍建议 `pip install` CLI）
- 内置目录 `~/.deepseek/skills` 仅在需要隔离时使用；一般不必复制一份
- MCP：见 [mcp.json.example](mcp.json.example)（推荐 `python -m multi_agent_memory.mcp_server`）；工具说明见 [../../skills/multi-agent-memory/references/mcp-tools.md](../../skills/multi-agent-memory/references/mcp-tools.md)
