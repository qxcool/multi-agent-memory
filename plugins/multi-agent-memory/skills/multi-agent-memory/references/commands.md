# 命令参考

以下示例中的脚本路径相对于插件根目录：

```powershell
python scripts/memory_hub.py --hub .ai-memory-hub doctor
```

全局参数必须放在子命令前：

- `--hub PATH`：指定记忆库，默认 `.ai-memory-hub`。
- `--json`：输出 JSON，便于代理或脚本继续处理。

## 初始化

```powershell
python scripts/memory_hub.py --hub .ai-memory-hub init
```

默认生成库内 `.gitignore`，防止记忆被意外提交。只有用户明确要求用 Git 共享记忆时才使用 `init --track`。

## 检索与上下文

```powershell
python scripts/memory_hub.py --hub .ai-memory-hub recall --query "认证 刷新令牌" --limit 8
python scripts/memory_hub.py --hub .ai-memory-hub context --query "认证" --max-chars 12000
```

`recall --no-archive` 排除归档任务；`context` 总是包含三份核心记忆，并附加活动记忆的相关片段。

## 任务状态

```powershell
python scripts/memory_hub.py --hub .ai-memory-hub status \
  --task auth-refresh --agent codex \
  --objective "修复刷新令牌并发问题" --state in-progress \
  --completed "确认重复刷新根因" \
  --next "补充并发测试" --blocker "无"
```

`--completed` 可以重复。再次调用时，未提供的字段保留原值。

## 候选记忆、索引和归档

```powershell
python scripts/memory_hub.py --hub .ai-memory-hub remember --agent codex --text "刷新请求必须共用单例 Promise" --tags "auth,concurrency"
python scripts/memory_hub.py --hub .ai-memory-hub reindex
python scripts/memory_hub.py --hub .ai-memory-hub archive --task auth-refresh
```

归档在目标已存在时拒绝覆盖，避免破坏历史记录。
