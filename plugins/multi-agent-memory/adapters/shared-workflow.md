# 各宿主共用节奏

Skill 正文只有一份；下列节奏对 **Claude / Codex / Cursor / DeepSeek / OpenCode / Qoder** 相同。  
把下方 `<agent>` 换成稳定短名：`claude` | `codex` | `cursor` | `deepseek` | `opencode` | `qoder`。

## 开场

```bash
memory-hub doctor
memory-hub orient --task <task> --agent <agent> --query "<固定检索词>" --objective "…"
# 将返回的 context 整段注入一次；勿叠 locate + context 双前缀
```

## 定位（防全仓检索）

```bash
memory-hub locate --query "<功能名或路径>"
```

1. **命中** → 打开返回的 `paths` / 跑 `commands`；**禁止**全仓 `rg` / Glob / find  
2. **未命中** → `map upsert` 补地图后再继续  
3. **架构 / 调用链 / 影响面** → 用 GitNexus（若已索引）；不要用全仓文本扫代替地图  

```bash
memory-hub map upsert --agent <agent> --feature "<名>" \
  --role "…" --path "…" --command "…"
# 可选：--authority "契约" --link "uses:feature:…"
```

## 交接 / 踩坑

```bash
memory-hub handoff --task <task> --agent <from> --to-agent <to>
memory-hub remember --agent <agent> --source-task <task> --type event \
  --tags "pitfall,lesson" --confidence confirmed \
  --key "pitfall:<主题>" --text "现象→原因→做法→勿再犯"
memory-hub feedback --id mem-… --signal useful
```

## 收尾

```bash
memory-hub close --task <task> --agent <agent>
memory-hub close --task <task> --agent <agent> --lesson "一行短教训" --archive
memory-hub close --task <task> --agent <agent> --evolve-maps
memory-hub map-health
```

## MCP（各宿主可选）

CLI 与 MCP 共用同一套 hub：`memory-hub-mcp` 或 `python -m multi_agent_memory.mcp_server`。

常用工具：`memory_orient` / `memory_handoff` / `memory_status` / `memory_overview` / `memory_locate`（含 hint + draft） / `memory_context` / `memory_map_upsert` / `memory_map_health` / `memory_close` / `memory_remember` / `memory_feedback` / `memory_evolve` / `memory_doctor`。

配置片段见各宿主目录下的 `mcp*.example`；通用 stdio 回退见 [mcp.stdio.example.json](mcp.stdio.example.json)。

## 跨 OS（不限制环境）

宿主可装在不同机器、不同系统上；**每台机器各自**跑 `install.ps1`（Win）或 `install.sh`（macOS/Linux）。  
地图路径只用仓库相对路径（正斜杠）；全局库用本机 `MEMORY_HUB_ROOT`，勿写死另一台机的盘符。

详见 [cross-platform.md](cross-platform.md)。
