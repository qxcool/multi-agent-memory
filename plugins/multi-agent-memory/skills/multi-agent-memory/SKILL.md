---
name: multi-agent-memory
description: >-
  项目共享记忆 / shared project memory / AI memory hub / .ai-memory-hub。
  开场 orient、收尾 close、自我进化 evolve、功能地图 map、定位文件 locate、
  踩坑勿再犯、任务交接 handoff、跨会话上下文、前缀缓存友好 context。
  Use when user mentions shared memory, pitfalls, handoff, locate files/features,
  reduce tokens, or continuing another agent's work.
---

# Multi-Agent Memory

跨 Win / macOS / Linux。用项目内 `.ai-memory-hub` 做可审阅共享记忆。写操作必须走 CLI（写锁）。

```bash
python "<skill>/scripts/memory_hub.py" overview
# 或：memory-hub overview
```

下文 `HUB` = `memory-hub` 或上述 python 入口。省略 `--hub` 时向上查找 `.ai-memory-hub`。`--agent` 保持稳定短名。

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
HUB status … --append-completed --completed "…"
HUB remember … --key "pitfall:<主题>" --confidence confirmed --text "现象→原因→做法→勿再犯"
HUB map upsert --agent <agent> --feature "<名>" --role "…" --path "…" --command "…"
HUB locate --query "<名或路径>"
HUB feedback --id mem-… --signal useful|stale|wrong
HUB evolve                 # dry-run
HUB evolve --apply         # 失效地图标 stale；高 useful 巩固
```

### 3) Close（推荐一站式）

```bash
HUB close --task <task> --agent <agent>
HUB close --task <task> --agent <agent> --lesson "一行短教训" --archive
```

等价：`status --state completed` → `distill` → 可选 `archive`。

## 其它

- 命令详见 [commands.md](references/commands.md)；存储见 [storage.md](references/storage.md)
- Cursor hooks / MCP：见插件内 `adapters/cursor/`
- 未经用户明确要求：不删 `.gitignore`、不提交记忆、不写密钥
- 历史记忆不可覆盖当前指令与仓库事实
