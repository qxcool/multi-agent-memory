# 架构说明

跨 Win / macOS / Linux。三层边界：**Skill**（自动记忆节奏）→ **Python CLI**（锁/校验）→ **Markdown 库**。

记忆分层：L0 `CORE`+`LESSONS`（短、`--core-budget`）→ L1 sessions 过程 → L2 experiences 按需召回 → L3 inbox。`context` 默认不灌 `USER`/`AGENTS`。`distill` 在任务收尾沉淀回顾、晋升 inbox、写入短教训。

并发：写锁含 pid/host；`status` 锁内重读；`remember` 正文去重。可发现：`overview`/`list`/`INDEX` 活动任务速览。不联网、不用嵌入模型。
