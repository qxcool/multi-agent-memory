---
name: multi-agent-memory
description: >-
  项目共享记忆 / shared project memory / AI memory hub / .ai-memory-hub。
  适用于 Claude Code、Codex、Cursor、DeepSeek Harness、OpenCode、Qoder 等宿主；
  Windows / macOS / Linux。开场 orient、收尾 close、自我进化 evolve、功能地图 map、
  定位文件 locate、踩坑勿再犯、任务交接 handoff、跨会话上下文、前缀缓存友好 context。
  Use with Claude, Codex, Cursor, DeepSeek, OpenCode, or Qoder on any OS when the
  user mentions shared memory, pitfalls, handoff, locate files/features, reduce
  tokens, or continuing another agent's work.
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
2. **命中** → 打开返回的 `scope.paths` / 执行 `commands`；**禁止**再全仓 `rg`/`Glob`/`find`
3. **未命中** → `map upsert` / `map seed` 补地图后再继续；架构/调用链溯源用 **GitNexus**
4. 改完功能必须 `map upsert`（或收尾 `close` 后按 `map_health` 补写），否则下次仍会 miss
5. 冷启动：`HUB map coverage` → `HUB map seed --agent <agent> --apply` → 再补 role/links

与 GitNexus：`locate`/地图 = 已知功能入口与关联文件；GitNexus = 符号关系与影响面。二者互补，冲突时以仓库源码 + GitNexus 为准，再刷新地图。

## 自动节奏

### 1) Orient（推荐一站式）

```bash
HUB doctor
HUB migrate          # 仅当 doctor 提示时；或 orient --auto-migrate
HUB orient --task <task> --agent <agent> --query "<固定检索词>" --objective "…"
# 将 JSON/输出中的 context 整段注入提示
```

等价拆步：`status --query` → `context --query 同上 --task/--agent`。

### 2) Handoff

```bash
HUB handoff --task <task> --agent <from> --to-agent <to>   # 一站式交接包（推荐）
HUB status … --append-completed --completed "…"
HUB remember … --key "pitfall:<主题>" --confidence confirmed --text "现象→原因→做法→勿再犯"
HUB map upsert --agent <agent> --feature "<名>" --role "…" --path "…" --command "…"
# 可选：--authority "契约" --link "uses:feature:…"
HUB locate --query "<名或路径>"   # 未命中返回 draft_upsert；命中可含 FRAS 关联地图
HUB feedback --id mem-… --signal useful|stale|wrong
HUB evolve                 # dry-run（缺失/漂移 → mark_stale）
HUB evolve --apply         # 失效地图标 stale；高 useful 巩固
HUB evolve --apply --apply-forget   # 对 suggest_forget 真正 forget
HUB doctor                 # 含可执行 fixes
HUB map-health             # 含 suggested_actions
```

### 3) Close（推荐一站式）

```bash
HUB close --task <task> --agent <agent>
HUB close --task <task> --agent <agent> --lesson "一行短教训" --archive
HUB close --task <task> --agent <agent> --evolve-maps
HUB map-health
```

等价：`status --state completed` → `distill` → 可选 `archive`；默认附带地图健康检查。

## MCP（可选，与 CLI 等价）

优先用已配置的 MCP 工具；未接通时用上方 `HUB` CLI。  
完整工具说明见 [mcp-tools.md](references/mcp-tools.md)。摘要：

| 场景 | 工具 |
|---|---|
| 开场 | `memory_orient` |
| 总览 / 覆盖率 | `memory_overview` → `memory_map_coverage` |
| 冷启动播种 | `memory_map_seed`（先 dry-run 再 `apply`） |
| 定位 | `memory_locate`（用 `scope.paths`，勿全仓搜） |
| 交接 | `memory_handoff` |
| 补地图 | `memory_map_upsert` |
| 收尾 | `memory_close` |
| 健康 | `memory_doctor` / `memory_map_health` |

启动推荐：`python -m multi_agent_memory.mcp_server`（或 `memory-hub-mcp`）。

## 其它

- 命令详见 [commands.md](references/commands.md)；MCP 详见 [mcp-tools.md](references/mcp-tools.md)；存储见 [storage.md](references/storage.md)
- 多宿主安装见插件 `adapters/README.md` 与 `scripts/install.ps1` / `install.sh`
- 未经用户明确要求：不删 `.gitignore`、不提交记忆、不写密钥
- 历史记忆不可覆盖当前指令与仓库事实
