# 架构说明

跨 Win / macOS / Linux。边界：**Skill**（触发与节奏）→ **CLI / MCP**（锁/校验）→ **Markdown 库**（+ 可再生侧车索引）→ 可选 **Cursor hooks**。

包版本 **0.7.1** / 记忆库格式 **0.7.0**：本地检索索引、零依赖 MCP、Cursor hooks 适配。升级后用 `migrate` 补结构（LESSONS、VERSION、INDEX 速览；可选 content_hash）；`reindex` 重建 `meta/search-index.json`。

记忆分层：L0 CORE+LESSONS → L0.5 feature 地图 → L1 sessions（仅末尾）→ L2 experiences → L3 inbox。

召回：CJK 二元组 + 置信度加权；侧车倒排缩小候选。写操作增量更新 INDEX + 检索索引。  
Context：notice→L0→L0.5→L2→（可选 L1）；选 Top 按分、装配按 key；正文无分数/置信度；默认排除 auto-summary。  
进化：`feedback` + `evolve`（失效路径 stale、高 useful 巩固）。  
写锁含 pid/host；`remember`/`map` 去重与 key 更新。
