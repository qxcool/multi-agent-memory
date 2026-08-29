# 自动记忆与分层上下文 v0.4

## 目标

1. 每次任务默认留下过程与踩坑，减少「下次再犯」。
2. 核心记忆与经验记忆分层装配，控制 token。
3. Win / macOS / Linux 同一套 Python CLI 与 Skill，不绑特定 shell。

## 分层

- L0：`memory/CORE.md` + `memory/LESSONS.md`（短，受 `--core-budget` 限制）
- L1：`sessions/<task>/<agent>.md`（过程轨迹）
- L2：`experiences/`（完整踩坑/决策，按 query 召回）
- L3：`inbox/`（候选，默认不进 context）

`context` 默认只装 L0（预算内）+ 按 query 优先召回 experiences，再补其它命中。`USER.md` / `AGENTS.md` 需显式 `--include-user` / `--include-agents`。

## 自动节奏（Skill）

开场：Orient → 分层 context → status 开写。  
过程：进展 append-completed；踩坑立刻 remember（tag `pitfall`/`lesson`）。  
收尾：`distill` 沉淀 retrospective + 晋升本任务 inbox；可选 `--lesson` 写入 LESSONS。

## distill

确定性、无 LLM：从 status 生成 experiences 回顾文件；晋升 `source_task` 匹配的 inbox；`--lesson` 追加 LESSONS 一行。
