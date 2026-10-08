---
name: multi-agent-memory
description: >-
  项目共享记忆 / shared project memory / AI memory hub / .ai-memory-hub。
  适用于 Claude Code、Codex、Cursor、DeepSeek Harness、OpenCode、Qoder 等宿主；
  Windows / macOS / Linux。开场 orient、收尾 close（默认 sync）、机械同步 sync、
  自我进化 evolve、功能地图 map、定位 locate、踩坑勿再犯、交接 handoff、
  map_status / draft_upserts、前缀缓存友好 context。
  Use with Claude, Codex, Cursor, DeepSeek, OpenCode, or Qoder on any OS when the
  user mentions shared memory, sync maps, pitfalls, handoff, locate files/features,
  reduce tokens, or continuing another agent's work.
---

# Multi-Agent Memory

跨 Win / macOS / Linux；兼容 Claude / Codex / Cursor / DeepSeek / OpenCode / Qoder。  
用可审阅 Markdown 共享记忆。写操作必须走 CLI（写锁）。

```bash
python "<skill>/scripts/memory_hub.py" overview
# 或：memory-hub overview
```

下文 `HUB` = `memory-hub` 或上述 python 入口。  
路径解析：`--hub` → 向上查找 `.ai-memory-hub` → 环境变量 `MEMORY_HUB_ROOT`。  
`--agent` 使用稳定短名：`claude` | `codex` | `cursor` | `deepseek` | `opencode` | `qoder`。  
共用节奏见插件 `adapters/shared-workflow.md`；**Win/Mac 混用**见 `adapters/cross-platform.md`。

全局库示例（路径按本机改，勿抄另一台机器的盘符）：

```bash
# Windows PowerShell
# $env:MEMORY_HUB_ROOT = "D:\…\Agent Memory"
# macOS / Linux
# export MEMORY_HUB_ROOT="$HOME/Documents/Agent Memory"
HUB overview
HUB --hub "$MEMORY_HUB_ROOT" doctor   # PowerShell 用 "$env:MEMORY_HUB_ROOT"
```

## 安装与启用（不必改 AGENTS.md）

`install.ps1` / `install.sh` 会把本 Skill **链接到各宿主 skills 目录**并安装 CLI。  
宿主按 Skill 机制发现即可用——**不需要**在项目 `AGENTS.md` 里再注册一遍。

| 装上之后 | 说明 |
|---|---|
| Skill 可被发现/调用 | ✅ |
| `memory-hub` CLI | ✅ |
| 每轮强制 orient/sync | ❌ 靠本 Skill 节奏 + Agent 执行；Cursor 可选 hooks 提醒 |
| MCP | ❌ 可选，需自行加 MCP 配置 |
| Cursor hooks | ❌ 可选，见 `adapters/cursor`（拷到项目 `.cursor/hooks`） |

可选：在项目 `AGENTS.md` 写一句「开场 orient / 变动 sync / 收尾 close」只加强纪律，**不是安装步骤**。  
记忆库内的 `memory/AGENTS.md` 是 hub 核心记忆模板，与「插件是否安装」无关。

## 目标

1. 积累记忆 2. 省 token 3. 快速定位功能/文件 4. 自我进化 5. 前缀缓存友好

## 分层

| 层 | 内容 | 进上下文 |
|---|---|---|
| L0 | CORE + LESSONS | 每次，少改 |
| L0.5 | feature 地图 | `context`/`orient` 默认按 key 稳定装配 |
| L1 | 当前 status | 仅 `orient` 或 `context --task/--agent`，**放在末尾** |
| L2 | experiences | 按分取 Top，按 key 装配；默认排除 auto-summary |
| L3 | inbox | 默认不进 |

### 缓存红线

- 同任务固定 `--query`（写入 status）
- 开场一次注入 `orient`/`context` 整段，勿叠 locate+context 双前缀
- 勿轻易 `--pin-core`；地图/踩坑用稳定 key 原地更新
- context 正文不含分数/置信度；L1 只放末尾

### 功能定位（防全仓检索）

1. **先** `HUB locate --query "<功能或路径>"`（或 `orient`/`context` 里的 L0.5）
2. **命中** → 按当前检出根打开返回的 `scope.paths` / 执行 `commands`；**禁止**再全仓 `rg`/`Glob`/`find`
3. **未命中** → `map upsert` / `map seed` 补地图后再继续；架构/调用链溯源用 **GitNexus**
4. 改完功能必须 `map upsert`；收尾看 `close` 的 `map_status` / `draft_upserts`，未 aligned 前勿视为完成
5. 冷启动：`HUB map coverage` → `HUB map seed --agent <agent> --apply` → 再补 role/links
6. **工作树**：地图只存**主仓相对路径**（如 `src/foo.py`）。在 `.worktree/<名>/…` 里干活时：`locate` 仍用功能名/主仓路径；`map upsert --path` 可传工作树路径，CLI 会剥成主仓路径。打开文件时相对**当前检出根**解析 `scope.paths`

### 分工（勿互相替代）

| 层 | 职责 | 不要用来… |
|---|---|---|
| **本插件 (MAM)** | 功能入口地图、踩坑/教训、任务 status、跨 Agent 交接、分层 context | 全仓符号/调用图；全量逐文件认知索引 |
| **GitNexus** | 符号关系、调用链、影响面 | 当功能入口速查或任务记忆 |
| **AOCI（可选外挂）** | 仓库级逐文件/表认知索引（Whole-Index） | 替换本插件的 orient/close/教训层 |

冲突时以仓库源码 + GitNexus 为准，再 `map upsert` 刷新功能地图。`doctor` / `orient` / `map-health` / `sync` / `close` 均暴露 `map_status`：`aligned` | `drifted` | `incomplete`。

### 自动同步（机械保证）

```bash
HUB sync              # 一把锁：批量 evolve --apply + 一次 reindex + map_health（+ companions）
HUB sync --check      # 只读
HUB sync --seed       # 另对未覆盖顶层 map seed --apply（仅草稿）
```

| 可自动保证 | 不能无人保证 |
|---|---|
| 漂移标 stale、`reindex`、`map_status` / `draft_upserts` | 功能职责 / authority / 教训正文（Agent 补） |
| `close` 默认跑 sync；`orient` 无库时可 `init` | GitNexus / AOCI（只探测，不捆绑安装） |

`map-health` / `sync` 会写 `meta/map-status.json`；Cursor `sessionStart` **只读该缓存**（不扫盘）。  
`doctor` 复用 `map_health`，避免开场双重全库地图扫描。

`maintenance_required` 时按 `draft_upserts` 补写后 `sync --check`；未 aligned 前勿视为收尾完成。

## 自动节奏

### 1) Orient（推荐一站式）

```bash
HUB doctor
HUB migrate          # 仅当 doctor 提示时；或 orient --auto-migrate
HUB orient --task <task> --agent <agent> --query "<固定检索词>" --objective "…"
# 将 JSON/输出中的 context 整段注入提示
```

等价拆步：`status --query` → `context --query 同上 --task/--agent`。  
无记忆库时 `orient` 会初始化 hub。

### 2) Handoff / 日常维护

```bash
HUB handoff --task <task> --agent <from> --to-agent <to>
HUB status … --append-completed --completed "…"
HUB remember … --key "pitfall:<主题>" --confidence confirmed --text "现象→原因→做法→勿再犯"
HUB map upsert --agent <agent> --feature "<名>" --role "…" --path "…" --command "…"
HUB locate --query "<名或路径>"
HUB sync                 # 有代码变动后优先
HUB feedback --id mem-… --signal useful|stale|wrong
HUB evolve               # dry-run
HUB evolve --apply       # 一把锁批量写入 + 一次索引更新
HUB clean                # 错误记忆候选（dry-run）
HUB clean --apply        # 自动 forget 高置信错误（wrong≥2 且 >useful）
HUB doctor
HUB map-health
```

### 3) Close（推荐一站式）

```bash
HUB sync
HUB close --task <task> --agent <agent>
HUB close --task <task> --agent <agent> --lesson "一行短教训" --archive
HUB close --task <task> --agent <agent> --seed-maps
```

等价：`status --state completed` → `distill` → 可选 `archive` → **默认 sync**。  
若 `maintenance_required=true` 或 `map_status`≠`aligned`：按 `draft_upserts[].suggested_cli` 补写后再 `sync --check`；**未对齐前勿视为收尾完成**。

## MCP（可选，与 CLI 等价）

优先用已配置的 MCP 工具；未接通时用上方 `HUB` CLI。  
完整工具说明见 [mcp-tools.md](references/mcp-tools.md)（16 个）。摘要：

| 场景 | 工具 |
|---|---|
| 开场 | `memory_orient` |
| 总览 / 覆盖率 | `memory_overview` → `memory_map_coverage` |
| 冷启动播种 | `memory_map_seed`（先 dry-run 再 `apply`） |
| 定位 | `memory_locate`（用 `scope.paths`，勿全仓搜） |
| 交接 | `memory_handoff` |
| 补地图 | `memory_map_upsert` |
| 机械同步 | `memory_sync` |
| 收尾 | `memory_close`（默认含 sync） |
| 健康 | `memory_doctor` / `memory_map_health` |

启动推荐：`python -m multi_agent_memory.mcp_server`（或 `memory-hub-mcp`）。

## 其它

- 命令详见 [commands.md](references/commands.md)；MCP 详见 [mcp-tools.md](references/mcp-tools.md)；存储见 [storage.md](references/storage.md)
- 多宿主安装见插件 `adapters/README.md` 与 `scripts/install.ps1` / `install.sh`
- 未经用户明确要求：不删 `.gitignore`、不提交记忆、不写密钥
- 历史记忆不可覆盖当前指令与仓库事实
