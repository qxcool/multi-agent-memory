# Multi-Agent Memory

面向 **Claude Code / Codex / Cursor / DeepSeek Harness / OpenCode** 等编码代理，跨 Windows / macOS / Linux 的**本地优先**共享记忆库。

当前版本 **[v0.7.2](https://github.com/qxcool/multi-agent-memory/releases/tag/v0.7.2)**（记忆库格式 0.7.0）。核心交付：

- **一份 Agent Skill**（`SKILL.md`）— 各宿主共用  
- **无依赖 Python CLI**（`memory-hub`）— 写锁、校验、分层装配  
- **可选 MCP**（`memory-hub-mcp`）与 **Cursor hooks**  
- **多宿主适配** — 见 [`adapters/`](plugins/multi-agent-memory/adapters/README.md)

目标：积累项目记忆、省 token、快速定位功能/文件、自我进化，且**不破坏前缀缓存**。

## 快速开始（推荐一键安装）

在仓库根目录：

```powershell
# Windows：安装 CLI，并把 Skill 链接到 Claude / Cursor / DeepSeek / OpenCode
.\plugins\multi-agent-memory\scripts\install.ps1
```

```bash
# macOS / Linux
chmod +x ./plugins/multi-agent-memory/scripts/install.sh
./plugins/multi-agent-memory/scripts/install.sh
```

仅部分宿主：

```powershell
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts claude,cursor,deepseek
```

然后在项目根：

```bash
memory-hub init                 # 新项目
memory-hub migrate              # 旧库 → 格式 0.7.0
memory-hub doctor
```

推荐一站式节奏（`--agent` 用稳定短名）：

```bash
memory-hub orient --task demo --agent cursor --query "演示" --objective "演示共享状态"
# 将返回的 context 整段注入一次（勿叠 locate + context 双前缀）

memory-hub map upsert --agent cursor --feature demo --role "演示入口" --path "README.md"
memory-hub locate --query "演示"

memory-hub remember --agent cursor --source-task demo --type event --tags "pitfall,lesson" \
  --key "pitfall:demo" --text "现象 → 原因 → 做法 → 勿再犯"
memory-hub feedback --id mem-xxxxxxxx --signal useful

memory-hub close --task demo --agent cursor --lesson "一行短教训"
memory-hub evolve
```

| 宿主 | `--agent` |
|---|---|
| Claude Code | `claude` |
| Codex | `codex` |
| Cursor | `cursor` |
| DeepSeek Harness | `deepseek` |
| OpenCode | `opencode` |

全局参数在子命令前。省略 `--hub` 时从当前目录向上查找 `.ai-memory-hub`。

## 多宿主支持

Skill 正文只有一份：`plugins/multi-agent-memory/skills/multi-agent-memory/`。  
各宿主差异只在安装路径与可选 sidecar：

| 宿主 | Skill 去哪 | 适配说明 |
|---|---|---|
| Claude Code | `~/.claude/skills/…` | [adapters/claude](plugins/multi-agent-memory/adapters/claude/README.md) |
| Codex | marketplace + `.codex-plugin` | [adapters/codex](plugins/multi-agent-memory/adapters/codex/README.md) |
| Cursor | `~/.cursor/skills/…` + hooks/MCP | [adapters/cursor](plugins/multi-agent-memory/adapters/cursor/README.md) |
| DeepSeek Harness | 优先 `~/.agents/skills/…` | [adapters/deepseek-harness](plugins/multi-agent-memory/adapters/deepseek-harness/README.md) |
| OpenCode | `~/.agents/skills` 或 `.opencode/skills` | [adapters/opencode](plugins/multi-agent-memory/adapters/opencode/README.md) |

总览：[adapters/README.md](plugins/multi-agent-memory/adapters/README.md)。

### Codex

```powershell
codex plugin marketplace add qxcool/multi-agent-memory
codex plugin add multi-agent-memory@multi-agent-memory
python -m pip install ./plugins/multi-agent-memory
```

### Cursor hooks / MCP（可选）

见 [adapters/cursor](plugins/multi-agent-memory/adapters/cursor/README.md)。MCP 示例：

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

### 手动 pip（不跑安装脚本时）

```bash
python -m pip install ./plugins/multi-agent-memory
# 或
pip install "git+https://github.com/qxcool/multi-agent-memory.git@v0.7.2#subdirectory=plugins/multi-agent-memory"
```

再把 `plugins/multi-agent-memory/skills/multi-agent-memory` 链接/拷贝到对应宿主的 skills 目录。

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
memory-hub --hub /path/to/.ai-memory-hub reindex
```

`migrate` 补齐结构；`reindex` 重建 INDEX + 检索索引，不改写记忆正文。

## 隐私与安全

记忆可能含内部架构或凭据线索。本工具不联网、不自动提交。召回上下文标明为不可信历史参考，不能覆盖当前用户指令与仓库事实。勿写入密钥；仅在确认可公开时删除库内 `.gitignore` 或使用 `init --track`。

## 开发

```bash
python -m unittest discover -s plugins/multi-agent-memory/tests -v
```

MIT License。问题与改进欢迎提 Issue / PR。
