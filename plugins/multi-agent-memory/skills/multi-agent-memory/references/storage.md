# 存储格式与兼容约束

记忆库完全由 UTF-8 Markdown 文件组成：

```text
.ai-memory-hub/
├── memory/        长期核心：CORE / LESSONS（短）+ USER / AGENTS（按需）
├── sessions/      活动任务过程（每任务每代理）
├── experiences/   完整经验与踩坑（按需召回）
├── wiki/          项目知识条目
├── inbox/         尚未整理的候选记忆
├── archive/       已归档任务与 forgotten/
└── INDEX.md       总索引（含活动任务速览）
```

任务文件沿用旧版字段：`目标`、`步骤`、`已完成`、`当前状态`、`阻塞`、`下一步`。可读旧版手工 Markdown，不会自动改写正文。只有 `status`、`remember`、`reindex` 和 `archive` 会写入。

## 结构化记忆元数据

`remember` 创建的新记忆在正文前包含兼容 YAML 的 JSON 标量前置元数据：

```yaml
---
id: "mem-c41e3c44e7b94e8fbc9c2fc5c366e9ff"
type: "decision"
source_task: "auth-refresh"
source_agent: "cursor"
created_at: "2026-08-29T16:30:00+08:00"
confidence: "confirmed"
tags: ["auth", "concurrency"]
links: [{"relation": "requires", "target": "mem-auth-client"}]
---
```

- 类型：`note`、`fact`、`decision`、`event`、`skill`、`task`、`preference`。
- 置信度：`unspecified`、`tentative`、`inferred`、`confirmed`。
- 关系：`related_to`、`requires`、`solved_by`、`uses`、`patches`、`conflicts_with`。

- ID 在创建时生成且不随文件名变化。关系目标保存记忆 ID 或调用方能够稳定解析的标识。本版本存储和统计显式关系；召回时若关系两端同时命中则小幅加分。
- 新记忆可带稳定 `key`；相同正文幂等跳过（返回已有条目），相同 `key` 原地更新并写 `updated_at`。
- `content_hash` 为正文规范化短哈希，用于去重。
- `distill` 默认写 `experiences/` 软回顾（`inferred` / `auto-summary` / `key=retrospective:…`），不自动改 LESSONS/CORE。
- `context` 对 L2 先按相关度取 Top，再按 `key`/`id`/`path` 稳定排序，减轻前缀缓存抖动。
- `forget` 将条目移入 `archive/forgotten/`，默认召回与列表不展示。

没有前置元数据的旧文件按 `legacy` 类型参与检索。`doctor` 和 `stats` 可以报告覆盖率，但不会自动改写旧文件。

所有写操作先获取库根目录的 `.memory-hub.lock`（含 pid/host/created），再在目标目录写临时文件并用原子替换完成提交。持锁进程已退出或超过两分钟的锁可被回收；`doctor` 会报告陈旧锁。`status` 在锁内重读再合并写入。

任务名、来源任务名和代理名不能包含路径分隔符、空段或控制字符。全文检索跳过 `.git`、`node_modules`、非 UTF-8 文件和大于 2 MB 的单个 Markdown 文件。
