# Multi-Agent Memory v0.3 设计

## 目标

在 Markdown 唯一事实源、默认不联网、旧库无需迁移的前提下：

1. 任意 AI/脚本进入项目后能快速知道库里有什么（可发现）。
2. 多软件、多脚本并发写入时更难写坏或互相覆盖（并发安全）。
3. 补齐召回过滤、关系加分与可逆遗忘（生命周期）。

## 可发现性

- `overview`：活动任务摘要、inbox 数量、各集合计数、最近候选记忆。
- `list <collection>`：列出 sessions / inbox / experiences / wiki / memory；支持 `--type` / `--tag` / `--json`。
- 根 `INDEX.md` 增加「活动任务速览」区块（任务、代理、状态、目标一行）。
- Skill 增加 **Orient**：陌生项目先 `doctor` → `overview`。

## 并发安全

- 写锁 payload：`pid`、`host`、`created`；持锁进程已不存在则立即回收。
- `status` 在锁内重新读取再合并写入，避免完成项互盖。
- `remember` 对正文规范化后的短哈希去重：同库已存在相同正文则拒绝并返回已有路径提示。

## 召回与遗忘

- `recall` / `context` 可选过滤：`--type`、`--tag`、`--confidence`、`--collection`。
- 若查询命中带 `links` 的记忆，对其 `target` 已在结果集中的条目小幅加分，并在 reason 中标注。
- `forget --id|--path`：移入 `archive/forgotten/`，不物理删除；默认 `list`/`recall` 不含 forgotten（`recall` 仍受 `--no-archive` 约束；forgotten 在 archive 下）。

## 非目标

Embedding、联网、宿主自动注入、替换 Markdown 事实源、全量图排序。
