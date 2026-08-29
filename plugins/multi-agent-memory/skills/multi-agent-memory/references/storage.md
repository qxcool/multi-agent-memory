# 存储格式与兼容约束

记忆库完全由 UTF-8 Markdown 文件组成：

```text
.ai-memory-hub/
├── memory/        长期核心记忆
├── sessions/      活动任务，每个任务和代理一份状态文件
├── experiences/   已整理的可复用经验
├── wiki/          项目知识条目
├── inbox/         尚未整理的候选记忆
├── archive/       已归档任务和历史材料
└── INDEX.md       总索引
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

ID 在创建时生成且不随文件名变化。关系目标保存记忆 ID 或调用方能够稳定解析的标识。本版本存储和统计显式关系，但不执行图遍历或 PageRank。

没有前置元数据的旧文件按 `legacy` 类型参与检索。`doctor` 和 `stats` 可以报告覆盖率，但不会自动改写旧文件。

所有写操作先获取库根目录的 `.memory-hub.lock`，再在目标目录写临时文件并用原子替换完成提交。超过两分钟的锁被视为陈旧锁；`doctor` 会报告它，下一次写入会清理它。

任务名、来源任务名和代理名不能包含路径分隔符、空段或控制字符。全文检索跳过 `.git`、`node_modules`、非 UTF-8 文件和大于 2 MB 的单个 Markdown 文件。
