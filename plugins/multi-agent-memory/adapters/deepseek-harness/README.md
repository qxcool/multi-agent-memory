# DeepSeek Harness 适配

DeepSeek Harness 按约定发现 Agent Skills（大致优先级）：

1. `<workspace>/.agents/skills`
2. `<workspace>/skills`
3. `<workspace>/.opencode/skills`
4. `<workspace>/.claude/skills`
5. `<workspace>/.cursor/skills`
6. `~/.agents/skills`
7. `~/.claude/skills`
8. `~/.deepseek/skills`

## 推荐安装

优先装到共享目录（Claude / OpenCode / DeepSeek 都能扫到）：

```text
~/.agents/skills/multi-agent-memory  →  <plugin>/skills/multi-agent-memory
```

```powershell
.\plugins\multi-agent-memory\scripts\install.ps1 -Hosts deepseek
```

也可在项目内：

```text
<workspace>/.agents/skills/multi-agent-memory  →  同上
```

CLI 侧：

```bash
pip install ./plugins/multi-agent-memory
memory-hub orient --task <task> --agent deepseek --query "…" --objective "…"
```

## 其它入口

- Harness：`/skill install github:qxcool/multi-agent-memory`（若宿主支持 GitHub 技能安装，装完后仍建议 `pip install` CLI）
- 内置目录 `~/.deepseek/skills` 仅在需要隔离时使用；一般不必复制一份

## 说明

- `--agent deepseek` 保持稳定，便于与其它宿主交接同一 task。
- MCP：若 Harness 支持 stdio MCP，可挂 `memory-hub-mcp`。
