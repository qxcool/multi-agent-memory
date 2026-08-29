# Multi-Agent Memory

面向任意编码代理（Cursor、Claude Code、Codex、OpenCode 等）的本地优先共享记忆。用普通 Markdown 保存长期项目事实、任务进度、经验、Wiki 和代理交接，无需数据库、账号或云服务。

核心交付是可移植的 **Agent Skill**（工作流）+ **无依赖 Python CLI**（读写）。宿主插件清单仅为可选安装适配。

## 特点

- 多代理共享：同一任务下，每个代理维护独立状态文件。
- 本地优先：默认阻止 `.ai-memory-hub` 被 Git 意外提交。
- 可审阅：所有数据都是 UTF-8 Markdown，可直接阅读和修改。
- 可追溯：新记忆记录稳定 ID、类型、来源、置信度、标签和显式关系。
- 可解释召回：返回相关度分数、命中原因和来源信息，并支持最低分过滤。
- 预算控制：生成上下文时按字符或近似 Token 预算选择完整记忆区块。
- 并发安全：跨平台写锁、同目录临时文件和原子替换。
- 旧版兼容：支持原 `memory_hub.py` 的 `recall`、`status`、`remember`、`reindex` 和 `archive` 调用。
- 零运行时依赖：仅需 Python 3.10 或更高版本。

## 作为通用 Skill 使用

将目录 `plugins/multi-agent-memory/skills/multi-agent-memory` 安装到你的代理 Skill 目录（或按所用工具的 Skill 安装方式注册）。代理按 `SKILL.md` 选择 Bootstrap / Load / Handoff / Remember / Close 分支，并通过本包内脚本调用 CLI。

CLI 入口（任选其一）：

```bash
# 已 pip 安装时
memory-hub --hub .ai-memory-hub doctor

# Skill 旁脚本（推荐在未安装包时使用）
python plugins/multi-agent-memory/skills/multi-agent-memory/scripts/memory_hub.py --hub .ai-memory-hub doctor

# 兼容旧路径
python plugins/multi-agent-memory/scripts/memory_hub.py --hub .ai-memory-hub doctor
```

常用命令：

```bash
python plugins/multi-agent-memory/skills/multi-agent-memory/scripts/memory_hub.py --hub .ai-memory-hub init
python plugins/multi-agent-memory/skills/multi-agent-memory/scripts/memory_hub.py --hub .ai-memory-hub status \
  --task demo --agent cursor --objective "演示共享状态" --state in-progress \
  --completed "初始化完成" --next "继续实现" --blocker "无"
python plugins/multi-agent-memory/skills/multi-agent-memory/scripts/memory_hub.py --hub .ai-memory-hub recall --query "演示"
python plugins/multi-agent-memory/skills/multi-agent-memory/scripts/memory_hub.py --hub .ai-memory-hub context --query "演示" --token-budget 2048
python plugins/multi-agent-memory/skills/multi-agent-memory/scripts/memory_hub.py --hub .ai-memory-hub stats
```

安装为全局命令：

```bash
python -m pip install ./plugins/multi-agent-memory
memory-hub --hub .ai-memory-hub doctor
```

## 安装到 Codex（可选适配）

```powershell
codex plugin marketplace add qxcool/multi-agent-memory
codex plugin add multi-agent-memory@multi-agent-memory
```

重新打开任务后即可让代理初始化或检索共享记忆。行为与通用 Skill 相同。

## 数据结构

```text
.ai-memory-hub/
├── memory/        核心长期记忆
├── sessions/      活动任务状态
├── experiences/   可复用经验
├── wiki/          项目知识
├── inbox/         候选记忆
├── archive/       历史归档
└── INDEX.md       总索引
```

完整命令和存储约束见 [命令参考](plugins/multi-agent-memory/skills/multi-agent-memory/references/commands.md) 与 [存储格式](plugins/multi-agent-memory/skills/multi-agent-memory/references/storage.md)。

新建记忆可声明结构化语义，同时仍保存为普通 Markdown：

```bash
python plugins/multi-agent-memory/skills/multi-agent-memory/scripts/memory_hub.py --hub .ai-memory-hub remember \
  --agent cursor --text "刷新请求必须复用同一个任务" \
  --type decision --source-task auth-refresh --confidence confirmed \
  --tags "auth,concurrency" --link "requires:mem-auth-client"
```

## 从旧版迁移

无需转换数据。先对原目录执行只读检查和检索：

```bash
python plugins/multi-agent-memory/skills/multi-agent-memory/scripts/memory_hub.py --hub /path/to/.ai-memory-hub doctor
python plugins/multi-agent-memory/skills/multi-agent-memory/scripts/memory_hub.py --hub /path/to/.ai-memory-hub recall --query "已知项目关键词"
```

确认结果后再运行 `reindex`。该命令只重建索引，不改写记忆正文。

## 隐私与安全

记忆中可能包含内部架构、客户信息或凭据线索。插件不会联网，也不会自动提交数据。召回上下文会明确标注为不可信历史参考，不能覆盖当前用户指令、系统约束和当前仓库事实。不要把密钥写入记忆；只有在确认内容可公开时，才删除库内 `.gitignore` 或使用 `init --track`。

## 开发

```bash
python -m unittest discover -s plugins/multi-agent-memory/tests -v
```

项目采用 MIT 许可证，欢迎提交问题与改进。
