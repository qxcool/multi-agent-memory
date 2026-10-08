# 各宿主共用节奏

Skill 正文只有一份；下列节奏对 **Claude / Codex / Cursor / DeepSeek / OpenCode / Qoder** 相同。  
把下方 `<agent>` 换成稳定短名：`claude` | `codex` | `cursor` | `deepseek` | `opencode` | `qoder`。

安装后 Skill 已在宿主 skills 目录，**不必**改项目 `AGENTS.md` 才能启用（hooks/MCP 仍可选）。

## 开场

```bash
memory-hub doctor
memory-hub overview                 # 含 map_coverage / companions
memory-hub sync --check             # 可选：看 map_status
memory-hub orient --task <task> --agent <agent> --query "<固定检索词>" --objective "…"
# 将返回的 context 整段注入一次；勿叠 locate + context 双前缀
```

冷启动（地图空）：

```bash
memory-hub map coverage
memory-hub map seed --agent <agent>          # 预览
memory-hub map seed --agent <agent> --apply  # 播种草稿后再补 role/links
```

## 定位（防全仓检索）

```bash
memory-hub locate --query "<功能名或路径>"
```

1. **命中** → 打开返回的 `scope.paths` / 跑 `commands`；**禁止**全仓 `rg` / Glob / find  
2. **未命中** → 用 `draft_upsert` 或 `map upsert` 补地图后再继续  
3. **工作树** → 地图写主仓相对路径；`--path .worktree/<名>/src/…` 会被剥成 `src/…`；打开文件相对当前检出根  
4. **架构 / 调用链 / 影响面** → 用 GitNexus（`scope.gitnexus_hint`）；不要用全仓文本扫代替地图  

```bash
memory-hub map upsert --agent <agent> --feature "<名>" \
  --role "…" --path "…" --command "…"
# 可选：--authority "契约" --link "uses:feature:…"
```

分工：本插件 = 功能入口 / 教训 / 交接；GitNexus = 符号图；AOCI（可选）= 全量文件认知。勿互相替代；**均不捆绑安装**（`doctor`/`sync` 只探测）。  
`doctor` / `orient` / `map-health` / `sync` 看 `map_status`（`aligned` | `drifted` | `incomplete`）。  
变动后：`memory-hub sync`（机械：evolve + reindex）；语义仍靠 Agent `map upsert`。

## 交接 / 踩坑

```bash
memory-hub handoff --task <task> --agent <from> --to-agent <to>
memory-hub remember --agent <agent> --source-task <task> --type event \
  --tags "pitfall,lesson" --confidence confirmed \
  --key "pitfall:<主题>" --text "现象→原因→做法→勿再犯"
memory-hub feedback --id mem-… --signal useful
```

## 收尾 / 同步

```bash
memory-hub sync
memory-hub sync --check
memory-hub close --task <task> --agent <agent>
memory-hub close --task <task> --agent <agent> --lesson "一行短教训" --archive
memory-hub close --task <task> --agent <agent> --seed-maps
```

`sync` / `close` 返回 `map_status` / `draft_upserts` / `maintenance_required` / `companions`。  
未 aligned 时按草稿 `map upsert`，**未补齐前勿视为收尾完成**。

## MCP（各宿主可选）

CLI 与 MCP 共用同一套 hub：`memory-hub-mcp` 或 `python -m multi_agent_memory.mcp_server`。

常用工具：`memory_orient` / `memory_handoff` / `memory_status` / `memory_overview` / `memory_locate`（含 scope） / `memory_map_coverage` / `memory_map_seed` / `memory_context` / `memory_map_upsert` / `memory_map_health` / `memory_sync` / `memory_close` / `memory_remember` / `memory_feedback` / `memory_evolve` / `memory_doctor`。

完整参数与场景：[skills/.../mcp-tools.md](../skills/multi-agent-memory/references/mcp-tools.md)。  
配置片段见各宿主目录下的 `mcp*.example`；通用 stdio 回退见 [mcp.stdio.example.json](mcp.stdio.example.json)。**推荐** `python -m multi_agent_memory.mcp_server`。

## 跨 OS（不限制环境）

宿主可装在不同机器、不同系统上；**每台机器各自**跑 `install.ps1`（Win）或 `install.sh`（macOS/Linux）。  
地图路径只用仓库相对路径（正斜杠）；全局库用本机 `MEMORY_HUB_ROOT`，勿写死另一台机的盘符。

详见 [cross-platform.md](cross-platform.md)。
