# Multi-Agent Memory

面向任意编码代理（Cursor / Codex / Claude Code 等）、跨 Windows / macOS / Linux 的**本地优先**共享记忆库。

当前版本 **[v0.7.1](https://github.com/qxcool/multi-agent-memory/releases/tag/v0.7.1)**（记忆库格式仍为 0.7.0）。核心交付：

- **Agent Skill** — 自动开场 / 交接 / 收尾节奏  
- **无依赖 Python CLI**（`memory-hub`）— 写锁、校验、分层装配  
- **可选 MCP**（`memory-hub-mcp`）与 **Cursor hooks**

目标：积累项目记忆、省 token、快速定位功能/文件、自我进化，且**不破坏前缀缓存**。

## 快速开始

```bash
# 1) 安装 CLI
python -m pip install ./plugins/multi-agent-memory
# 或指定版本：pip install "git+https://github.com/qxcool/multi-agent-memory.git@v0.7.1#subdirectory=plugins/multi-agent-memory"

# 2) 把 Skill 拷到代理的 skills 目录
#    plugins/multi-agent-memory/skills/multi-agent-memory  →  ~/.claude/skills/ 等

# 3) 初始化或升级记忆库（在项目根目录）
memory-hub init
memory-hub migrate          # 旧库升级到格式 0.7.0
memory-hub doctor
```

推荐一站式节奏：

```bash
memory-hub orient --task demo --agent cursor --query "演示" --objective "演示共享状态"
# 将返回的 context 整段注入一次（勿叠 locate + context 双前缀）

memory-hub map upsert --agent cursor --feature demo --role "演示入口" --path "README.md"
memory-hub locate --query "演示"

memory-hub remember --agent cursor --source-task demo --type event --tags "pitfall,lesson" \
  --key "pitfall:demo" --text "现象 → 原因 → 做法 → 勿再犯"
memory-hub feedback --id mem-xxxxxxxx --signal useful

memory-hub close --task demo --agent cursor --lesson "一行短教训"
memory-hub evolve              # dry-run
```

全局参数在子命令前。省略 `--hub` 时从当前目录向上查找 `.ai-memory-hub`。

## 特点

| 能力 | 说明 |
|---|---|
| 多代理共享 | 同一任务下每代理独立 status；共享 wiki / experiences |
| 本地可审阅 | UTF-8 Markdown；默认 `.gitignore` 阻止误提交 |
| 分层上下文 | L0 CORE+LESSONS → L0.5 功能地图 → L2 经验；（L1 status 仅放末尾） |
| 前缀缓存友好 | 固定 `status --query`；选 Top 按分、装配按 key；正文不含分数/置信度 |
| 功能地图 | `map upsert` / `locate` / `map list`，减少每次扫仓库 |
| 自我进化 | `feedback` + `evolve`；`doctor` 提示失效路径 / 缺 distill |
| 本地检索索引 | `meta/search-index.json` 加速 recall/locate（Markdown 仍是真相源） |
| 零运行时依赖 | 仅需 Python ≥ 3.10；CJK 二元组召回 + 置信度加权 |
| 并发安全 | 跨平台写锁、原子替换 |

## Cursor hooks（可选）

适配文件在 [`plugins/multi-agent-memory/adapters/cursor/`](plugins/multi-agent-memory/adapters/cursor/)。

```powershell
# 项目级示例
New-Item -ItemType Directory -Force .cursor\hooks | Out-Null
Copy-Item plugins\multi-agent-memory\adapters\cursor\hooks\*.py .cursor\hooks\
```

`.cursor/hooks.json`：

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      { "command": "python .cursor/hooks/session_start.py", "timeout": 10 }
    ],
    "stop": [
      { "command": "python .cursor/hooks/stop.py", "timeout": 5, "loop_limit": 1 }
    ]
  }
}
```

- `sessionStart`：注入短提醒，并设置 `MEMORY_HUB_ROOT`
- `stop`：默认不自动跟进；设 `MEMORY_HUB_STOP_FOLLOWUP=1` 才提示 close/evolve

## MCP（可选）

```bash
memory-hub-mcp
# 或：python -m multi_agent_memory.mcp_server
```

工具：`memory_orient` / `memory_locate` / `memory_context` / `memory_map_upsert` / `memory_doctor`。

Cursor MCP 配置示例：

```json
{
  "mcpServers": {
    "multi-agent-memory": {
      "command": "memory-hub-mcp",
      "args": []
    }
  }
}
```

## 安装到 Codex（可选）

```powershell
codex plugin marketplace add qxcool/multi-agent-memory
codex plugin add multi-agent-memory@multi-agent-memory
```

重新打开任务后即可使用；行为与通用 Skill 相同。详见 [`adapters/codex/`](plugins/multi-agent-memory/adapters/codex/)。

## 数据结构

```text
.ai-memory-hub/
├── memory/        CORE + LESSONS（短）/ USER / AGENTS
├── sessions/      任务过程（含可选「检索词」）
├── experiences/   完整踩坑与回顾（按需召回）
├── wiki/          项目知识与 feature 地图
├── inbox/         候选
├── archive/       归档与 forgotten/
├── meta/          侧车检索索引（可再生）
└── INDEX.md       总索引 + 活动任务速览
```

更多说明：

- [命令参考](plugins/multi-agent-memory/skills/multi-agent-memory/references/commands.md)
- [存储格式](plugins/multi-agent-memory/skills/multi-agent-memory/references/storage.md)
- [架构说明](docs/architecture.md)

## 从旧版迁移

```bash
memory-hub --hub /path/to/.ai-memory-hub doctor
memory-hub --hub /path/to/.ai-memory-hub migrate --dry-run
memory-hub --hub /path/to/.ai-memory-hub migrate
memory-hub --hub /path/to/.ai-memory-hub reindex   # 重建 Markdown INDEX + search-index
```

`migrate` 补齐 LESSONS / VERSION / INDEX 速览等结构；`reindex` 不改写记忆正文。

## 隐私与安全

记忆可能含内部架构或凭据线索。本工具不联网、不自动提交。召回上下文标明为不可信历史参考，不能覆盖当前用户指令与仓库事实。勿写入密钥；仅在确认可公开时删除库内 `.gitignore` 或使用 `init --track`。

## 开发

```bash
python -m unittest discover -s plugins/multi-agent-memory/tests -v
```

MIT License。问题与改进欢迎提 Issue / PR。
