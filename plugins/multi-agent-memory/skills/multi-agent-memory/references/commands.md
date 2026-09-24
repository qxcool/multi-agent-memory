# 命令参考

跨 Win / macOS / Linux；宿主不限。`HUB` = `memory-hub` 或 `python`/`python3` + `scripts/memory_hub.py`。  
下文示例里的 `cursor` 可换成任意 `--agent` 短名（`claude` | `codex` | `cursor` | `deepseek` | `opencode` | `qoder`）。

全局参数在子命令前。省略 `--hub` 时向上查找 `.ai-memory-hub`。

## 一站式（推荐）

```bash
HUB orient --task auth --agent cursor --query "认证刷新" --objective "修刷新"
HUB handoff --task auth --agent cursor --to-agent claude
HUB close --task auth --agent cursor --lesson "刷新必须单例" --archive
HUB close --task auth --agent cursor --evolve-maps   # 收尾时顺带 evolve --apply
HUB map-health              # 只读：缺失/漂移/缺指纹 + suggested_actions
HUB evolve              # 扫描
HUB evolve --apply      # 写入 stale/confirm
HUB evolve --apply --apply-forget
```

`orient`：doctor →（可选 migrate）→ status（含检索词）→ context（含 L0.5 + 末尾 L1）。  
`close`：completed → distill → 可选 archive；默认附带 `map_health`（`--no-check-maps` 跳过；`--evolve-maps` 写入）。  
`evolve`：失效/漂移路径标 stale（写入 `stale_reason`）；高 useful 巩固；高 wrong 建议 forget。

## 发现与升级

```bash
HUB doctor
HUB migrate --dry-run
HUB migrate
HUB migrate --backfill-map-fingerprints
HUB overview
HUB map list
HUB map coverage
HUB map seed --agent cursor
HUB map-health
HUB list sessions
```

## 功能地图与定位

```bash
HUB map upsert --agent cursor --feature auth-refresh \
  --role "登录态刷新" --authority "刷新须单例 Promise" \
  --path "src/auth/refresh.ts" --command "npm test -- auth" \
  --link "uses:feature:auth-client"
HUB locate --query "认证刷新"     # 含 hits + scope + hint；命中勿全仓 rg
HUB map list
HUB map coverage                  # 未映射顶层热点
HUB map-health
HUB feedback --id mem-xxxxxxxx --signal stale --reason "路径已迁移"
```

定位纪律：命中 → 打开 `paths`；未命中 → `map upsert`；架构溯源 → GitNexus。

## 分层上下文（护缓存）

```bash
HUB context --query "认证刷新" --token-budget 2048 --core-budget 2000 --map-budget 1200
HUB context --query "认证刷新" --task auth --agent cursor   # L1 仅在末尾
HUB context --query "认证" --no-maps --include-inferred
HUB recall --query "勿再犯" --collection experiences --tag pitfall
```

## 任务过程

```bash
HUB status --task auth --agent cursor --objective "修刷新" --state in-progress --query "认证刷新"
HUB status --task auth --agent cursor --append-completed --completed "定位竞态"
HUB remember --agent cursor --source-task auth --type event \
  --tags "pitfall,lesson" --confidence confirmed \
  --key "pitfall:auth-refresh-singleton" \
  --text "重复刷新会打爆接口；必须复用单例 Promise"
HUB feedback --id mem-xxxxxxxx --signal useful
```

## 收尾

```bash
HUB distill --task auth --agent cursor
HUB distill --task auth --agent cursor --lesson "一行短教训" --pin-core
HUB archive --task auth
HUB close --task auth --agent cursor --archive
```

## 其它

```bash
HUB promote --to experiences --id mem-xxxxxxxx
HUB forget --id mem-xxxxxxxx
HUB stats
HUB reindex   # 重建 Markdown INDEX + meta/search-index.json
```

## MCP（可选）

```bash
memory-hub-mcp
# 或 python -m multi_agent_memory.mcp_server
```

工具：`memory_orient` / `memory_locate` / `memory_context` / `memory_map_upsert` / `memory_map_health` / `memory_close` / `memory_remember` / `memory_feedback` / `memory_evolve` / `memory_doctor`。

## 多宿主安装

见插件 [`adapters/README.md`](../../adapters/README.md)。跨 OS：[cross-platform.md](../../adapters/cross-platform.md)。

```bash
# Windows
..\..\scripts\install.ps1
# macOS / Linux
../../scripts/install.sh
```

`--agent` 短名：`claude` | `codex` | `cursor` | `deepseek` | `opencode` | `qoder`。
