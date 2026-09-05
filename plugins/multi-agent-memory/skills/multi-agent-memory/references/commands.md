# 命令参考

跨 Win / macOS / Linux。`HUB` = `memory-hub` 或 `python scripts/memory_hub.py`。

全局参数在子命令前。省略 `--hub` 时向上查找 `.ai-memory-hub`。

## 一站式（推荐）

```bash
HUB orient --task auth --agent cursor --query "认证刷新" --objective "修刷新"
HUB close --task auth --agent cursor --lesson "刷新必须单例" --archive
HUB evolve              # 扫描
HUB evolve --apply      # 写入 stale/confirm
```

`orient`：doctor →（可选 migrate）→ status（含检索词）→ context（含 L0.5 + 末尾 L1）。  
`close`：completed → distill → 可选 archive。  
`evolve`：失效路径标 stale；高 useful 巩固；高 wrong 建议 forget。

## 发现与升级

```bash
HUB doctor
HUB migrate --dry-run
HUB migrate
HUB overview
HUB map list
HUB list sessions
```

## 功能地图与定位

```bash
HUB map upsert --agent cursor --feature auth-refresh \
  --role "登录态刷新" --path "src/auth/refresh.ts" --command "npm test -- auth"
HUB locate --query "认证刷新"     # 含 missing_paths
HUB map list
```

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

工具：`memory_orient` / `memory_locate` / `memory_context` / `memory_map_upsert` / `memory_doctor`。