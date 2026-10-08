"""Hub 共享常量（格式版本见 HUB_FORMAT_VERSION；包版本见 pyproject）。"""

from __future__ import annotations

COLLECTIONS = ("memory", "sessions", "experiences", "wiki", "inbox", "archive")
LIST_COLLECTIONS = ("sessions", "inbox", "experiences", "wiki", "memory")
HUB_DIRNAME = ".ai-memory-hub"
HUB_FORMAT_VERSION = "0.7.0"
VERSION_FILENAME = "VERSION"
PROMOTE_TARGETS = {"memory", "experiences", "wiki"}
MEMORY_TYPES = {"note", "fact", "decision", "event", "skill", "task", "preference"}
CONFIDENCE_LEVELS = {"unspecified", "tentative", "inferred", "confirmed"}
FEEDBACK_SIGNALS = {"useful", "stale", "wrong"}
CONFIDENCE_SCORE_ADJUST = {
    "confirmed": 4,
    "tentative": 1,
    "unspecified": 0,
    "inferred": -2,
}
RELATION_TYPES = {"related_to", "requires", "solved_by", "uses", "patches", "conflicts_with"}
INDEXED_COLLECTIONS = ("wiki", "experiences", "inbox")
# key / 指纹去重只查活跃集合；不含 archive（forgotten 不得被 remember 原地复活）
ACTIVE_MEMORY_COLLECTIONS = frozenset({"inbox", "experiences", "wiki", "memory"})
CORE_MEMORY_FILES = {"CORE.md", "LESSONS.md", "USER.md", "AGENTS.md"}
CORE_FILE_TEMPLATES = {
    "memory/CORE.md": (
        "# Core Memory\n\n"
        "只记录长期稳定的项目事实与硬约束。长文踩坑写到 experiences，这里最多保留一行指针。\n"
    ),
    "memory/LESSONS.md": (
        "# Lessons\n\n"
        "一行一条：短教训或「勿再犯」指针。详情见 experiences/。\n"
    ),
    "memory/USER.md": "# User Memory\n\n仅记录用户明确要求长期保留的偏好。\n",
    "memory/AGENTS.md": "# Agent Memory\n\n记录代理协作约定、角色和交接规则。\n",
}
STATUS_FIELDS = {
    "目标": "objective",
    "步骤": "steps",
    "已完成": "completed",
    "当前状态": "state",
    "阻塞": "blocker",
    "下一步": "next_step",
    "检索词": "query",
}
