# 命令参考

`HUB` 为 `memory-hub`，或本技能目录下的 `python scripts/memory_hub.py`。全局参数放在子命令前。

```bash
HUB --hub .ai-memory-hub doctor
```

- `--hub PATH`：记忆库目录，默认 `.ai-memory-hub`
- `--json`：机器可读 JSON

## 初始化

```bash
HUB --hub .ai-memory-hub init
```

默认生成库内 `.gitignore`。只有用户明确要求用 Git 共享记忆时才使用 `init --track`。

## 检索与上下文

```bash
HUB --hub .ai-memory-hub recall --query "认证 刷新令牌" --limit 8
HUB --hub .ai-memory-hub recall --query "认证" --min-score 10
HUB --hub .ai-memory-hub context --query "认证" --max-chars 12000 --token-budget 2048
```

`recall --no-archive` 排除归档；`--min-score` 过滤低分结果。每条含命中原因与结构化来源。

`context` 先输出安全声明，再装配核心记忆与相关片段。`--max-chars` 与 `--token-budget` 同时给出时取更严限制。

## 任务状态

`--agent` 用当前宿主短名（如 `cursor`、`claude`、`codex`），同一项目内保持稳定。

```bash
HUB --hub .ai-memory-hub status \
  --task auth-refresh --agent cursor \
  --objective "修复刷新令牌并发问题" --state in-progress \
  --completed "确认重复刷新根因" \
  --next "补充并发测试" --blocker "无"
```

`--completed` 可重复。再次调用时，未提供的字段保留原值。

## 候选记忆、索引和归档

```bash
HUB --hub .ai-memory-hub remember \
  --agent cursor --text "刷新请求必须共用单例 Promise" \
  --tags "auth,concurrency" --type decision \
  --source-task auth-refresh --confidence confirmed \
  --link "requires:mem-auth-client"
HUB --hub .ai-memory-hub reindex
HUB --hub .ai-memory-hub archive --task auth-refresh
```

`--link` 可重复，格式 `relation:target`。类型、置信度、关系见 [存储格式](storage.md)。省略新参数时兼容旧调用：默认 `type=note`、`confidence=unspecified`。

归档在目标已存在时拒绝覆盖。

## 统计与健康检查

```bash
HUB --hub .ai-memory-hub stats
HUB --hub .ai-memory-hub --json doctor
```

`stats` 报告记录数、集合/类型分布、关系数、元数据覆盖率、活动与归档任务数。`doctor` 将缺元数据、索引可能过期列为警告；目录缺失、编码错误、陈旧写锁为问题。
