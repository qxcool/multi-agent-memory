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
2. 若提示格式版本落后或缺少 LESSONS：`HUB migrate`（可先 `HUB migrate --dry-run`；需要补哈希时加 `--backfill-hash`）
3. `HUB overview`（或读 `INDEX.md` 活动任务速览）
4. `HUB context --query "<任务关键词>" --token-budget 2048 --core-budget 2000`  
   需要偏好/协作约定时再加 `--include-user` / `--include-agents`
5. `HUB status --task <task> --agent <agent> --objective "…" --state in-progress …`

**完成：** 库结构已是当前格式；短核心 + 相关经验已加载；任务 status 已开写。

### 2) Handoff（过程中）

有进展：`HUB status … --append-completed --completed "…"`  
踩坑立刻（稳定主题用 `--key`，避免重复记）：

```bash
HUB remember --agent <agent> --source-task <task> --type event \
  --tags "pitfall,lesson" --confidence confirmed \
  --key "pitfall:<短主题>" \
  --text "现象 → 原因 → 正确做法 → 下次勿再犯"
```

功能/文件地图用稳定 key 更新，不要每次新建：

```bash
HUB remember --agent <agent> --type fact --tags "map,feature" \
  --key "feature:<功能名>" \
  --text "职责…\n关键路径：…\n相关命令：…"
# 需要长期可见时可：HUB promote --to wiki --id …
```

相同正文 → 跳过（`deduped`）；相同 `--key` → 原地更新（`updated`）。

**完成：** 过程不丢；踩坑已进 inbox（或已有相同正文则跳过）。

### 3) Close + Distill（收尾必做）

```bash
HUB status --task <task> --agent <agent> --state completed …
HUB distill --task <task> --agent <agent>
# 仅确认过的短教训才进 L0：
HUB distill --task <task> --agent <agent> --lesson "一行短教训"
# 极少数硬约束才：
HUB distill --task <task> --agent <agent> --lesson "…" --pin-core
HUB archive --task <task>   # 需要时
```

`distill` 默认写入 **软自动总结**（`confidence=inferred`，`key=retrospective:<task>:<agent>`，可覆盖更新），进 `experiences/`，**不写 LESSONS/CORE**。L0 少动，利于上下文前缀缓存；`context` 对 L2 按 key/id 稳定排序。

**完成：** 软回顾已沉淀；未经验证的内容不会变成硬引导。

## 其它

- `list` / `promote` / `forget` / `stats`：见 [命令参考](references/commands.md)
- 存储约定：见 [存储格式](references/storage.md)
- 未经用户明确要求：不删 `.gitignore`、不提交/外发记忆、不写密钥
- 历史记忆不可覆盖当前指令与仓库事实；`inferred` / `auto-summary` 只作观察草稿
