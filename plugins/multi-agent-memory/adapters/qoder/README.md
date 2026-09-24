# Qoder 适配

Qoder IDE / CLI 的 Skill 路径（官方文档）：

| 范围 | 路径 |
|---|---|
| 用户级 | `~/.qoder/skills/{name}/SKILL.md` |
| 项目级 | `<repo>/.qoder/skills/{name}/SKILL.md` |

## Skill

```text
~/.qoder/skills/multi-agent-memory  →  <plugin>/skills/multi-agent-memory
```

```powershell
# Windows
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts qoder
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts qoder -ProjectQoder -SkipPip
```

```bash
# macOS / Linux
./plugins/multi-agent-memory/scripts/install.sh --hosts qoder
./plugins/multi-agent-memory/scripts/install.sh --hosts qoder --project-qoder --skip-pip
```

项目级（可选）：

```text
<repo>/.qoder/skills/multi-agent-memory  →  同上
```

装完后在 Qoder 中执行 `/skills reload`（若会话已开）。

## `--agent`

稳定短名：`qoder`。

## 节奏与定位纪律

见 [../shared-workflow.md](../shared-workflow.md)。摘要：

```bash
memory-hub orient --task <task> --agent qoder --query "…" --objective "…"
memory-hub locate --query "…"          # 命中则勿全仓 rg
memory-hub map upsert --agent qoder --feature "…" --path "…"
memory-hub close --task <task> --agent qoder
```

## MCP（可选）

用户级：`~/.qoder/settings.json` → `mcpServers`  
项目级：`<repo>/.mcp.json` 或 `.qoder/settings.json`

示例见 [mcp.json.example](mcp.json.example)。入口不在 PATH 时用 [../mcp.stdio.example.json](../mcp.stdio.example.json)。

## Hooks（可选）

Qoder 支持 `UserPromptSubmit` / `Stop` 等 hooks（见官方 Hooks 文档）。  
本插件不强制安装 hooks；需要时可在 settings 的 `hooks` 段自行引用短提醒脚本，原则与 Cursor 相同：**只提醒，不自动灌全文**（护前缀缓存）。
