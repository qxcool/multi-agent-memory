# 命令参考

`HUB` 为 `memory-hub`，或本技能目录下的 `python scripts/memory_hub.py`。全局参数放在子命令前。

```bash
HUB doctor
HUB --hub /path/to/.ai-memory-hub doctor
```

- `--hub PATH`：省略或为 `.ai-memory-hub` 时，从当前目录向上查找；自定义相对/绝对路径按字面使用。
- `--json`：机器可读 JSON。

## 初始化

```bash
HUB init
```

默认生成库内 `.gitignore`。只有用户明确要求用 Git 共享记忆时才使用 `init --track`。

## 检索与上下文

```bash
HUB recall --query "认证 刷新令牌" --limit 8
HUB recall --query "认证" --min-score 10
HUB context --query "认证" --token-budget 2048
HUB context --query "认证" --full --token-budget 4096
```

`recall --no-archive` 排除归档；`--min-score` 过滤低分结果。`context --full` 装入召回文件的完整正文（仍受预算限制）。

## 任务状态

`--agent` 用当前宿主短名（如 `cursor`、`claude`、`codex`），同一项目内保持稳定。

只读：

```bash
HUB status --task auth-refresh --agent cursor
```

写入（追加完成项）：

```bash
HUB status --task auth-refresh --agent cursor \
  --objective "修复刷新令牌并发问题" --state in-progress \
  --append-completed --completed "确认重复刷新根因" \
  --next "补充并发测试" --blocker "无"
```

不加 `--append-completed` 时，`--completed` 会整表替换已完成列表。省略的其他字段保留原值。

## 候选记忆、晋升、归档

```bash
HUB remember \
  --agent cursor --text "刷新请求必须共用单例 Promise" \
  --tags "auth,concurrency" --type decision \
  --source-task auth-refresh --confidence confirmed \
  --link "requires:mem-auth-client"
HUB promote --to experiences --id mem-xxxxxxxx
HUB promote --to wiki --path inbox/2026-08-29-....md
HUB archive --task auth-refresh
HUB reindex
```

`--link` 可重复，格式 `relation:target`。晋升目标：`experiences`、`wiki`、`memory`。只能从 `inbox/` 晋升。

## 统计与健康检查

```bash
HUB stats
HUB --json doctor
```

`doctor` 将缺元数据、索引可能过期列为警告；目录缺失、编码错误、陈旧写锁为问题。
