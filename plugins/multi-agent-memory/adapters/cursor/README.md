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
安装后 Cursor 即可发现本 Skill，**不必**在项目 `AGENTS.md` 再注册。hooks / MCP 仍需按下面可选步骤配置。

## `--agent`

稳定短名：`cursor`（hooks 提醒里也用此短名）。

## Hooks（项目级，可选）

```powershell
# Windows（一键）
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts cursor -CursorHooks
# 或手动：
New-Item -ItemType Directory -Force .cursor\hooks | Out-Null
Copy-Item plugins\multi-agent-memory\adapters\cursor\hooks\*.py .cursor\hooks\
Copy-Item plugins\multi-agent-memory\adapters\cursor\hooks.json .cursor\hooks.json
```

```bash
# macOS / Linux（一键；仅有 python3 时会改 hooks.json）
./plugins/multi-agent-memory/scripts/install.sh --hosts cursor --cursor-hooks
# 或手动：
mkdir -p .cursor/hooks
cp plugins/multi-agent-memory/adapters/cursor/hooks/*.py .cursor/hooks/
cp plugins/multi-agent-memory/adapters/cursor/hooks.json .cursor/hooks.json
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

- `sessionStart`：短提醒 + 若有 hub 则**只读** `meta/map-status.json` 缓存（不扫盘）+ `MEMORY_HUB_ROOT` / `MEMORY_HUB_SKILL`
- `stop`：**默认跟进** sync/close + draft_upserts；`MEMORY_HUB_STOP_FOLLOWUP=0` 关闭（`loop_limit: 1`）

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
