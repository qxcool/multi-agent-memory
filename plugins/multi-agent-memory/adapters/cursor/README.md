# Cursor 适配

## Skill

```text
~/.cursor/skills/multi-agent-memory  →  <plugin>/skills/multi-agent-memory
```

```powershell
# Windows
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts cursor
# 项目级 Skill：
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts cursor -ProjectCursor -SkipPip
```

```bash
# macOS / Linux
./plugins/multi-agent-memory/scripts/install.sh --hosts cursor
./plugins/multi-agent-memory/scripts/install.sh --hosts cursor --project-cursor --skip-pip
```

项目级也可手动放在 `<repo>/.cursor/skills/multi-agent-memory`。

## `--agent`

稳定短名：`cursor`（hooks 提醒里也用此短名）。

## Hooks（项目级，可选）

```powershell
# Windows
New-Item -ItemType Directory -Force .cursor\hooks | Out-Null
Copy-Item plugins\multi-agent-memory\adapters\cursor\hooks\*.py .cursor\hooks\
Copy-Item plugins\multi-agent-memory\adapters\cursor\hooks.json .cursor\hooks.json
```

```bash
# macOS / Linux
mkdir -p .cursor/hooks
cp plugins/multi-agent-memory/adapters/cursor/hooks/*.py .cursor/hooks/
cp plugins/multi-agent-memory/adapters/cursor/hooks.json .cursor/hooks.json
# 若本机只有 python3：把 hooks.json 里的 python 改成 python3
```

或编辑 `.cursor/hooks.json`（默认 `python`；Unix 常改为 `python3`）：

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

- `sessionStart`：短提醒（先 locate、命中勿 rg、与 GitNexus 分工）+ `MEMORY_HUB_ROOT` / `MEMORY_HUB_SKILL`
- `stop`：默认不跟进；`MEMORY_HUB_STOP_FOLLOWUP=1` 时提示 close / map upsert / evolve（`loop_limit: 1`）

> 部分 Cursor 版本对 `sessionStart.additional_context` 有竞态；完整上下文请用 `memory-hub orient`。

## MCP（可选）

合并用户或项目 MCP 配置，示例见 [mcp.json.example](mcp.json.example)。  
**推荐** `python -m multi_agent_memory.mcp_server`（Cursor 常不含 Scripts PATH）；`memory-hub-mcp` 亦可。  
工具说明：[../../skills/multi-agent-memory/references/mcp-tools.md](../../skills/multi-agent-memory/references/mcp-tools.md)；stdio 回退见 [../mcp.stdio.example.json](../mcp.stdio.example.json)。

## 节奏与定位纪律

见 [../shared-workflow.md](../shared-workflow.md)。摘要：

```bash
memory-hub orient --task <task> --agent cursor --query "…" --objective "…"
memory-hub locate --query "…"
memory-hub close --task <task> --agent cursor
```
