# 跨平台（不限制环境）

同一份 Skill + CLI 可在 **Windows / macOS / Linux** 与任意支持的宿主上并行使用。宿主装在哪台机、哪个 OS，**互不影响**；共享的是 Markdown 记忆库与仓库相对路径约定。

## 每台机器各自安装

| OS | 安装 |
|---|---|
| Windows | `.\plugins\multi-agent-memory\scripts\install.ps1` |
| macOS / Linux | `./plugins/multi-agent-memory/scripts/install.sh` |

脚本会：`pip install` CLI，并把 Skill **链接**到本机各宿主目录（Win=junction，Unix=symlink）。

```bash
# 验证（两台机器都要能跑）
memory-hub doctor
# 或：python -m multi_agent_memory.cli doctor
# macOS 若无 python 命令：python3 -m pip install … / python3 -m multi_agent_memory.cli …
```

Codex 仍走 marketplace；与 OS 无关。

## 记忆库放哪（Win ↔ Mac 协作）

推荐优先级：

1. **仓库内 `.ai-memory-hub/`（默认）**  
   各机 clone 同一仓库后，在项目根跑 `memory-hub` 即可；路径解析向上查找，无需设环境变量。  
   默认 `.gitignore` 阻止提交；若团队要共享记忆，可改忽略规则并接受冲突/合并成本。

2. **本机全局库 + `MEMORY_HUB_ROOT`**  
   适合个人跨项目长期记忆（如 Obsidian 库）。**每台机器设自己的绝对路径**，不要把另一台机的盘符路径写进文档当唯一真相。

```powershell
# Windows（用户环境变量或会话）
$env:MEMORY_HUB_ROOT = "D:\Software\03_Database\multi-agent-memory\Agent Memory"
memory-hub --hub "$env:MEMORY_HUB_ROOT" doctor
```

```bash
# macOS / Linux
export MEMORY_HUB_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Agent Memory"
# 或：export MEMORY_HUB_ROOT="$HOME/Documents/Agent Memory"
memory-hub --hub "$MEMORY_HUB_ROOT" doctor
```

3. **云同步盘（iCloud / OneDrive / Syncthing）挂同一全局库**  
   可以，但**避免两台机器同时写**（写锁按本机 pid/host，挡不住另一台机的同步冲突）。串行使用，或优先用「每仓一份」方案。

路径解析顺序：`--hub` → 向上找 `.ai-memory-hub` → `MEMORY_HUB_ROOT`。

## 路径纪律（跨 OS 关键）

| 要做 | 不要做 |
|---|---|
| `map upsert --path "src/auth/refresh.ts"`（仓库相对、正斜杠） | `--path "D:\proj\src\..."` / `/Users/me/proj/...` |
| 命令写跨平台或注明 OS：`npm test` / `pytest` | 把仅 Win 的 `.\foo.ps1` 当成 Mac 也能跑的唯一命令 |
| 地图路径大小写与仓库一致（macOS 默认大小写不敏感，Linux 敏感） | 依赖「Windows 不区分大小写」写错路径 |

CLI 会把 `\` 规范成 `/`，并拒绝绝对路径；指纹按**文件内容**算，与 OS 无关。

## 环境变量与 shell 差异

| | Windows (PowerShell) | macOS / Linux |
|---|---|---|
| 用户主目录 | `$env:USERPROFILE` / `~` | `$HOME` / `~` |
| Skill 例 | `%USERPROFILE%\.cursor\skills\…` | `~/.cursor/skills/…` |
| 引用 hub | `"$env:MEMORY_HUB_ROOT"` | `"$MEMORY_HUB_ROOT"` |
| Python | 通常 `python` | 常为 `python3` |

MCP 配置里的 `command`：推荐 `python`/`python3` + `-m multi_agent_memory.mcp_server`（宿主常不含 Scripts）；也可用 PATH 上的 `memory-hub-mcp`。

## `--agent` 与主机无关

短名只标识**代理身份**（`cursor` / `claude` / …），**不**编码 OS。  
Win 上的 Cursor 与 Mac 上的 Cursor 若交接同一 task，都用 `--agent cursor`（或约定不同短名如 `cursor-win` / `cursor-mac`——仅在你需要区分机器时）。

## 检查清单

- [ ] 当前 OS 已跑对应 install 脚本  
- [ ] `memory-hub doctor` 能发现目标 hub  
- [ ] 功能地图只有仓库相对路径  
- [ ] 跨机同步时没有双写同一全局库  
- [ ] 各宿主能加载同一份 Skill（无分叉拷贝）
