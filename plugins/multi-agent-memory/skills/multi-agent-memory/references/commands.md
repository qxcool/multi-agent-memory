# 命令参考

跨 Win / macOS / Linux。`HUB` = `memory-hub` 或：

```bash
python scripts/memory_hub.py
```

全局参数在子命令前。省略 `--hub` 时向上查找 `.ai-memory-hub`。

## 发现与升级

```bash
HUB doctor
HUB migrate --dry-run
HUB migrate
HUB migrate --backfill-hash
HUB overview
HUB list sessions
HUB list inbox --tag pitfall
```

升级插件后，对已有 `.ai-memory-hub` 先 `migrate`：补 LESSONS、forgotten 目录、VERSION、重建带活动任务速览的 INDEX；不覆盖已有 CORE/USER 正文。

## 分层上下文（省 token）

```bash
HUB context --query "认证 刷新" --token-budget 2048 --core-budget 2000
HUB context --query "认证" --full --include-user --include-agents
HUB recall --query "勿再犯" --collection experiences --tag pitfall
```

默认 L0 只含 `CORE.md` + `LESSONS.md`（受 `--core-budget`）。`USER` / `AGENTS` 需显式打开。无 `--collection` 时优先召回 `experiences/`。

## 任务过程

```bash
HUB status --task auth-refresh --agent cursor --objective "修刷新" --state in-progress
HUB status --task auth-refresh --agent cursor --append-completed --completed "定位竞态"
HUB remember --agent cursor --source-task auth-refresh --type event \
  --tags "pitfall,lesson" --confidence confirmed \
  --key "pitfall:auth-refresh-singleton" \
  --text "重复刷新会打爆接口；必须复用单例 Promise"
```

相同正文会幂等返回（`deduped`）；同一 `--key` 则原地更新（`updated`），不堆重复条目。

## 收尾沉淀

```bash
HUB distill --task auth-refresh --agent cursor --lesson "刷新必须单例，禁止并行重入"
HUB distill --task auth-refresh --agent cursor --lesson "…" --pin-core
HUB archive --task auth-refresh
```

`distill` 会写 experiences 回顾，并晋升 `source_task` 匹配的 inbox（可用 `--no-promote-inbox` 关闭）。

## 其它

```bash
HUB promote --to experiences --id mem-xxxxxxxx
HUB forget --id mem-xxxxxxxx
HUB stats
```
