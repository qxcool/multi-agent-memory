# 架构说明

跨 Win / macOS / Linux。边界：**Skill**（多宿主共用）→ **CLI / MCP** → **Markdown 库**（+ 侧车索引）→ 可选 **Cursor hooks**。宿主适配见 `plugins/multi-agent-memory/adapters/`（Claude / Codex / Cursor / DeepSeek / OpenCode / Qoder）；共用节奏见 `adapters/shared-workflow.md`；跨 OS 混用见 `adapters/cross-platform.md`。

核心包拆分：`hub.py`（记忆写读 / migrate / status）+ `index.py`（search-index/reindex/stats）+ `assembly.py`（recall/context）+ `lifecycle.py`（orient/sync/close/evolve/clean/doctor/distill）+ `maps.py` + `constants.py` + `companions.py` + `util.py` / `errors.py`；CLI/MCP 仍从 `hub` 导入，API 不变。

包版本以 `pyproject.toml` 为准（**0.7.6**）；记忆库格式 **0.7.0**（`HUB_FORMAT_VERSION`）。升级后用 `migrate` 补结构；`reindex` 重建 `meta/search-index.json`。一键安装：`scripts/install.ps1` / `install.sh`（`-CursorHooks` / `--cursor-hooks` 可选装 Cursor hooks；**不必**改项目 `AGENTS.md`）。MCP / hooks 为可选 sidecar。

记忆分层：L0 CORE+LESSONS → L0.5 feature 地图 → L1 sessions（仅末尾）→ L2 experiences → L3 inbox。

召回：CJK 二元组 + 置信度加权；侧车倒排（v2：watermark + dirty 标记；增量写只标脏，读时再建）。`_find_by_key` 优先走索引。  
Context：notice→L0→L0.5→L2→（可选 L1）；选 Top 按分、装配按 key；正文无分数/置信度；默认排除 auto-summary。  
机械同步：`sync` = 锁外规划 + **一把写锁**内批量 `evolve --apply` + **一次** `reindex`，再 `map_health`；写 `meta/map-status.json`。语义地图仍靠 Agent `map upsert`；改完可用 `map maintain --path …`。  
进化 / 清理：`feedback` → `clean`（wrong≥2 且 >useful → `archive/forgotten`）；`sync --apply-forget` / `evolve --apply --apply-forget` 可选自动 forget。  
功能地图：FRAS + `path_fingerprints`；`map_status`（aligned|drifted|incomplete）+ `draft_upserts`；`locate` 含 `scope`。  
`doctor` 复用 `map_health`；`overview` 含覆盖率与 `companions`（只探测不安装）。  
MCP：19 工具（含 `memory_sync` / `memory_recall` / `memory_map_maintain` / `memory_clean`）；`close` 默认 sync。  
Cursor `sessionStart` 只读 `meta/map-status.json`，不扫盘。  
写锁含 pid/host；`remember`/`map` 去重与 key 更新。
