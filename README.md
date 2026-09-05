# Multi-Agent Memory

面向任意编码代理、任意操作系统（Windows / macOS / Linux）的本地优先共享记忆。每次任务留下过程与踩坑，核心记忆与经验分层装配以节省 token。

核心交付：**Agent Skill（自动开场/收尾节奏）** + **无依赖 Python CLI**。多脚本经写锁；`overview` / `INDEX.md` 让其他 AI 知道库里有什么。

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
- 中文友好召回：无空格中文查询按字二元组匹配，并对 `confirmed` / `inferred` 置信度加权。
- 增量索引：写入只刷新受影响集合的 INDEX，全量 `reindex` 仍可用。
- 功能地图：`map upsert` / `locate` / `map list` 快速定位职责与关联文件，减少每次扫仓库。
- 自我进化：`feedback useful|stale|wrong` 巩固或降权记忆。
- 前缀缓存友好：固定 `status --query`、context 稳定装配、默认排除 auto-summary。
- 一站式闭环：`orient` 开场、`close` 收尾、`evolve` 自我进化扫描。
- 本地检索索引：`meta/search-index.json` 加速 recall/locate（Markdown 仍是真相源）。
- 可选 MCP：`memory-hub-mcp` 暴露 orient/locate/context/map/doctor。
- Cursor hooks 适配：`adapters/cursor/`（sessionStart 提醒；stop 可选跟进）。

## 作为通用 Skill 使用

1. 安装 CLI 包（Skill 脚本也依赖该包，或需能从仓库解析到 `src/`）：

```bash
python -m pip install ./plugins/multi-agent-memory
```

2. 将目录 `plugins/multi-agent-memory/skills/multi-agent-memory` 安装到你的代理 Skill 目录。

代理按 `SKILL.md` 选择 Bootstrap / Load / Handoff / Remember / Curate / Close。省略 `--hub` 时会从当前目录向上查找 `.ai-memory-hub`。

CLI 入口（任选其一）：

```bash
memory-hub doctor
python plugins/multi-agent-memory/skills/multi-agent-memory/scripts/memory_hub.py doctor
python plugins/multi-agent-memory/scripts/memory_hub.py doctor
```

常用命令：

```bash
memory-hub orient --task demo --agent cursor --query "演示" --objective "演示共享状态"
memory-hub map upsert --agent cursor --feature demo --role "演示入口" --path "README.md"
memory-hub locate --query "演示"
memory-hub map list
memory-hub evolve
memory-hub remember --agent cursor --source-task demo --type event --tags "pitfall,lesson" \
  --key "pitfall:demo" --text "现象 → 原因 → 做法 → 勿再犯"
memory-hub feedback --id mem-xxxxxxxx --signal useful
memory-hub close --task demo --agent cursor --lesson "一行短教训"
memory-hub stats
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
├── memory/        CORE + LESSONS（短）/ USER / AGENTS
├── sessions/      任务过程
├── experiences/   完整踩坑与回顾（按需召回）
├── wiki/          项目知识
├── inbox/         候选
├── archive/       归档与 forgotten/
├── meta/          侧车检索索引（可再生）
└── INDEX.md       总索引 + 活动任务速览
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
