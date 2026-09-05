# Claude Code 适配

## Skill

将插件内 Skill 链接到用户 Skill 目录（推荐 junction/symlink，勿复制分叉）：

```text
~/.claude/skills/multi-agent-memory  →  <plugin>/skills/multi-agent-memory
```

PowerShell：

```powershell
$src = Resolve-Path ..\..\skills\multi-agent-memory
$dst = "$env:USERPROFILE\.claude\skills\multi-agent-memory"
New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
if (Test-Path $dst) { Remove-Item $dst -Force -Recurse }
cmd /c mklink /J "$dst" "$src"
```

或运行仓库脚本：`scripts/install.ps1 -Hosts claude`。

## 节奏

```bash
memory-hub orient --task <task> --agent claude --query "<固定检索词>" --objective "…"
memory-hub close --task <task> --agent claude
```

## 说明

- Claude 通过 `SKILL.md` 的 `description` 触发；写操作走 `memory-hub`（写锁）。
- 若使用 CC Switch 同步技能，请保证最终指向本插件的 `skills/multi-agent-memory`，避免旧 checkout 分叉。
