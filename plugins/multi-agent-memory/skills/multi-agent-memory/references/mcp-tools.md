# MCP 工具说明（v0.7.4）

与 CLI 共用同一 `.ai-memory-hub`。推荐启动方式（宿主 PATH 常无 Scripts）：

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

也可用 `memory-hub-mcp`；macOS/Linux 可把 `python` 换成 `python3`。通用示例见 [`adapters/mcp.stdio.example.json`](../../../adapters/mcp.stdio.example.json)。

写操作经 hub 写锁；所有工具可选 `hub`（省略则向上查找 `.ai-memory-hub` / `MEMORY_HUB_ROOT`）。  
`--agent` 短名：`claude` | `codex` | `cursor` | `deepseek` | `opencode` | `qoder`。

## 何时用哪个

| 场景 | 工具 |
|---|---|
| 开场装配上下文 | `memory_orient` |
| 新会话了解项目 / 地图覆盖 | `memory_overview` → `memory_map_coverage` → 可选 `memory_map_seed` |
| 定位功能/文件（勿全仓搜） | `memory_locate` |
| 跨代理交接 | `memory_handoff` |
| 更新进度 / 固定检索词 | `memory_status` |
| 补写功能地图 | `memory_map_upsert` |
| 地图健康 / 缺指纹 / 漂移 | `memory_map_health` / `memory_doctor` |
| 收尾 | `memory_close` |
| 踩坑 / 投票 / 进化 | `memory_remember` / `memory_feedback` / `memory_evolve` |

节奏细节见 [shared-workflow.md](../../../adapters/shared-workflow.md)。

## 工具一览

### memory_orient

开场一站式：doctor → status → context（缓存友好）。  
**必填**：`task`, `agent`, `query`（同任务固定检索词）。  
**可选**：`objective`, `auto_migrate`, `hub`。  
**用法**：把返回的 `context` **整段**注入一次；勿再叠 `locate`+`context` 双前缀。

### memory_handoff

跨代理交接包：status + locate + 踩坑 + 地图问题。  
**必填**：`task`, `agent`（交出方）。  
**可选**：`to_agent`（默认同 agent）, `limit`, `hub`。  
接收方用交接包里的 **相同 query** 再 `memory_orient`。

### memory_status

读/写任务 status（进度、固定检索词、已完成条目）。  
**必填**：`task`, `agent`。  
**可选**：`objective`, `state`, `query`, `next_step`, `blocker`, `completed[]`, `append_completed`, `read_only`, `hub`。

### memory_overview

总览：计数、活动任务、地图问题、`map_coverage_pct` / `map_unmapped`、`continue_with` 续跑提示。  
**可选**：`hub`。

### memory_locate

按功能名/路径定位 feature 地图（含 FRAS 关联扩展）。  
**必填**：`query`。  
**可选**：`limit`, `hub`。  
**命中**：优先打开返回的 `scope.paths` / `commands`，**禁止**全仓 `rg`/`Glob`/`find`。  
**未命中**：用 `draft_upsert` 或 `memory_map_upsert` 补地图；架构/影响面用 GitNexus（见 `scope.gitnexus_hint`）。

### memory_context

装配分层上下文（L0→L0.5→L2，可选末尾 L1）。  
**可选**：`query`（可省略：若有 `task`+`agent` 则复用 status 固定检索词）, `token_budget`, `hub`。

### memory_map_upsert

写入/更新功能地图（稳定 key=`feature:<name>`；可带 authority/links/路径指纹）。  
**必填**：`agent`, `feature`。  
**可选**：`role`, `authority`, `paths[]`, `commands[]`, `note`, `links[]`（如 `uses:feature:auth`）, `hub`。  
仅**文件**路径有内容指纹；纯目录入口（如 `docs/`）不报缺指纹。

### memory_map_health

只读检查地图：缺失 / 漂移 / 缺指纹 / stale；含 `suggested_actions`（可执行 CLI）。  
**可选**：`limit`, `hub`。

### memory_map_coverage

对照仓库顶层（cwd）与功能地图覆盖率，列出未映射热点。  
**可选**：`max_unmapped`, `hub`。  
冷启动先看覆盖率，再决定是否 seed。

### memory_map_seed

按未覆盖顶层目录播种地图草稿。  
**必填**：`agent`。  
**可选**：`apply`（默认 false=dry-run）, `max_features`, `hub`。  
播种后应再补 `role` / `links`，并用 `memory_locate` 验证。

### memory_close

收尾：`completed` + distill；默认附带 `map_health`。  
**必填**：`task`, `agent`。  
**可选**：`lesson`, `archive`, `evolve_maps`, `check_maps`（默认 true）, `hub`。

### memory_remember

写入 inbox 候选（踩坑/决策等）；建议稳定 `key`（如 `pitfall:…`）。  
**必填**：`agent`, `text`。  
**可选**：`tags`（逗号分隔）, `type`, `key`, `confidence`, `source_task`, `hub`。

### memory_feedback

对记忆投票 `useful` / `stale` / `wrong`。  
**必填**：`signal`。  
**可选**：`id`（mem-…）或 `path`, `reason`, `hub`（`id`/`path` 至少其一）。

### memory_evolve

自我进化扫描。默认 dry-run；`apply` 写入 stale/confirm；`apply_forget` 可真正 forget。  
**可选**：`apply`, `apply_forget`, `hub`。

### memory_doctor

检查记忆库健康；返回 `warnings` 与可执行 `fixes`。  
**可选**：`hub`。

## 与 CLI 对应

| MCP | CLI |
|---|---|
| memory_orient | `memory-hub orient` |
| memory_handoff | `memory-hub handoff` |
| memory_status | `memory-hub status` |
| memory_overview | `memory-hub overview` |
| memory_locate | `memory-hub locate` |
| memory_context | `memory-hub context` |
| memory_map_upsert | `memory-hub map upsert` |
| memory_map_health | `memory-hub map-health` |
| memory_map_coverage | `memory-hub map coverage` |
| memory_map_seed | `memory-hub map seed` |
| memory_close | `memory-hub close` |
| memory_remember | `memory-hub remember` |
| memory_feedback | `memory-hub feedback` |
| memory_evolve | `memory-hub evolve` |
| memory_doctor | `memory-hub doctor` |

完整 CLI 见 [commands.md](commands.md)。
