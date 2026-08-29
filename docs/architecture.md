# 架构说明

跨 Win / macOS / Linux。三层边界：**Skill**（自动记忆节奏）→ **Python CLI**（锁/校验）→ **Markdown 库**。

升级后用 `migrate` 把旧库补到当前格式（LESSONS、VERSION、INDEX 速览；可选补 content_hash），不覆盖已有核心正文。`doctor` 发现落后时提示 migrate。

记忆分层：L0 `CORE`+`LESSONS` → L1 sessions → L2 experiences → L3 inbox。`distill` 收尾沉淀。写锁含 pid/host；`remember` 去重。
