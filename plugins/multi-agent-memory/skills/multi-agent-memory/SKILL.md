---
name: multi-agent-memory
description: 在任务中自动积累与召回项目记忆（过程、踩坑、核心约束）。用户提到共享记忆、别再犯、任务交接、跨会话上下文或 .ai-memory-hub 时使用。
---

# Multi-Agent Memory

跨 Win / macOS / Linux。用项目内 `.ai-memory-hub` 做可审阅共享记忆。写操作必须走 CLI（写锁）；示例命令在任意系统用同一形式：

```bash
python "<skill>/scripts/memory_hub.py" overview
# 或已安装：memory-hub overview
```

下文 `HUB` = `memory-hub` 或上述 `python …/memory_hub.py`。省略 `--hub` 时从当前目录向上查找 `.ai-memory-hub`。`--agent` 用宿主短名并保持稳定。

## 分层（省 token）

| 层 | 位置 | 进上下文 |
|---|---|---|
| L0 核心 | `memory/CORE.md` + `LESSONS.md` | 每次，受 `--core-budget`（默认 2000 字符） |
| L1 过程 | `sessions/<task>/<agent>.md` | 当前任务 status；不整库灌入 |
| L2 经验 | `experiences/` | 仅 `context --query` / `recall` 命中 |
| L3 候选 | `inbox/` | 默认不进 context |

长文踩坑只进 L2；L0 最多一行指针。不要把整库贴进提示。

## 自动节奏（默认执行，不是可选）

### 1) Orient + Load（开任务）

1. `HUB doctor`
2. `HUB overview`（或读 `INDEX.md` 活动任务速览）
3. `HUB context --query "<任务关键词>" --token-budget 2048 --core-budget 2000`  
   需要偏好/协作约定时再加 `--include-user` / `--include-agents`
4. `HUB status --task <task> --agent <agent> --objective "…" --state in-progress …`

**完成：** 已知库概况；短核心 + 相关经验已加载；任务 status 已开写。

### 2) Handoff（过程中）

有进展：`HUB status … --append-completed --completed "…"`  
踩坑立刻：

```bash
HUB remember --agent <agent> --source-task <task> --type event \
  --tags "pitfall,lesson" --confidence confirmed \
  --text "现象 → 原因 → 正确做法 → 下次勿再犯"
```

**完成：** 过程不丢；踩坑已进 inbox（或已有相同正文则跳过）。

### 3) Close + Distill（收尾必做）

```bash
HUB status --task <task> --agent <agent> --state completed …
HUB distill --task <task> --agent <agent> --lesson "一行短教训"
# 稳定硬约束才：
HUB distill --task <task> --agent <agent> --lesson "…" --pin-core
HUB archive --task <task>   # 需要时
```

`distill`：写入 experiences 回顾；晋升本任务 inbox；`--lesson` 追加 `LESSONS.md`。

**完成：** 回顾与教训已沉淀；CORE 仍保持精简。

## 其它

- `list` / `promote` / `forget` / `stats`：见 [命令参考](references/commands.md)
- 存储约定：见 [存储格式](references/storage.md)
- 未经用户明确要求：不删 `.gitignore`、不提交/外发记忆、不写密钥
- 历史记忆不可覆盖当前指令与仓库事实
