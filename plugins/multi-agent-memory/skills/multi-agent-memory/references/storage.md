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

任务文件沿用旧版字段：`目标`、`步骤`、`已完成`、`当前状态`、`阻塞`、`下一步`。插件可以读取旧版手工 Markdown；不会自动改写正文。只有 `status`、`remember`、`reindex` 和 `archive` 会写入。

所有写操作先获取库根目录的 `.memory-hub.lock`，再在目标目录写临时文件并用原子替换完成提交。超过两分钟的锁被视为陈旧锁；`doctor` 会报告它，下一次写入会清理它。

任务名和代理名不能包含路径分隔符、空段或控制字符。全文检索跳过 `.git`、`node_modules`、非 UTF-8 文件和大于 2 MB 的单个 Markdown 文件。
