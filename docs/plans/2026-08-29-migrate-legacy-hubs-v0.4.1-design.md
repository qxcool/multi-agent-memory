# 旧库迁移 v0.4.1

升级程序后，对已有 `.ai-memory-hub` 运行 `migrate`（幂等）：

- 补齐集合目录、`memory/LESSONS.md`、`archive/forgotten/`、默认 `.gitignore`
- 写入 `VERSION` 为目标格式版本
- 重建 INDEX（含活动任务速览）
- 可选 `--backfill-hash`：为已有 frontmatter 但缺 `content_hash` 的文件补哈希
- 不覆盖已有 CORE/USER/AGENTS/LESSONS 正文

`doctor` 在版本落后或缺少 LESSONS/速览时提示 migrate。
