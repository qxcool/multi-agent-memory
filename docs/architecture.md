# 架构说明

跨 Win / macOS / Linux。边界：**Skill**（多宿主共用）→ **CLI / MCP** → **Markdown 库**（+ 侧车索引）→ 可选 **Cursor hooks**。宿主适配见 `plugins/multi-agent-memory/adapters/`（Claude / Codex / Cursor / DeepSeek / OpenCode）。

包版本以 `pyproject.toml` 为准；记忆库格式 **0.7.0**。升级后用 `migrate` 补结构；`reindex` 重建 `meta/search-index.json`。一键安装：`scripts/install.ps1` / `install.sh`。

记忆分层：L0 CORE+LESSONS → L0.5 feature 地图 → L1 sessions（仅末尾）→ L2 experiences → L3 inbox。

召回：CJK 二元组 + 置信度加权；侧车倒排缩小候选。写操作增量更新 INDEX + 检索索引。  
Context：notice→L0→L0.5→L2→（可选 L1）；选 Top 按分、装配按 key；正文无分数/置信度；默认排除 auto-summary。  
进化：`feedback` + `evolve`（失效路径 stale、高 useful 巩固）。  
写锁含 pid/host；`remember`/`map` 去重与 key 更新。
