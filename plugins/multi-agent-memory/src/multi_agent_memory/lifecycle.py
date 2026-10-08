"""生命周期：orient / sync / close / evolve / clean / doctor。"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Sequence

from .companions import probe_companions
from .constants import (
    ACTIVE_MEMORY_COLLECTIONS,
    COLLECTIONS,
    HUB_FORMAT_VERSION,
    INDEXED_COLLECTIONS,
)
from .errors import MemoryHubError
from .maps import _inspect_map_paths, _map_upsert_cli, _normalize_path_fingerprints
from .util import (
    atomic_write,
    content_fingerprint,
    frontmatter,
    lock_owner_gone,
    normalize_memory_key,
    now,
    one_line,
    safe_segment,
    slug,
    split_frontmatter,
)


def _parse_version(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in value.strip().split("."):
        if piece.isdigit():
            parts.append(int(piece))
        else:
            digits = "".join(char for char in piece if char.isdigit())
            parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def _version_less(left: str, right: str) -> bool:
    a = _parse_version(left)
    b = _parse_version(right)
    width = max(len(a), len(b))
    a = a + (0,) * (width - len(a))
    b = b + (0,) * (width - len(b))
    return a < b

class LifecycleMixin:
    """开场/同步/收尾/进化/清理/体检（混入 MemoryHub）。"""

    def orient(
        self,
        *,
        task: str,
        agent: str,
        query: str,
        objective: str | None = None,
        state: str = "in-progress",
        token_budget: int | None = 2048,
        core_budget: int = 2000,
        map_budget: int = 1200,
        include_user: bool = False,
        include_agents: bool = False,
        include_maps: bool = True,
        include_inferred: bool = False,
        auto_migrate: bool = False,
    ) -> dict[str, object]:
        """开场一站式：可选 migrate、写入 status（含固定检索词）、返回缓存友好 context。"""
        self.root.mkdir(parents=True, exist_ok=True)
        if not (self.root / "memory").is_dir():
            self.init()
        query = one_line(query)
        if not query:
            raise MemoryHubError("开场检索词不能为空（用于稳定前缀缓存）")
        migrated = None
        doctor = self.doctor()
        if auto_migrate and any("migrate" in str(item) for item in doctor.get("warnings") or []):
            migrated = self.migrate()
            doctor = self.doctor()
        status = self.update_status(
            task=task,
            agent=agent,
            objective=objective if objective is not None else task,
            state=state,
            query=query,
        )
        context_text = self.context(
            query,
            token_budget=token_budget,
            core_budget=core_budget,
            map_budget=map_budget,
            include_user=include_user,
            include_agents=include_agents,
            include_maps=include_maps,
            include_inferred=include_inferred,
            session_task=task,
            session_agent=agent,
        )
        map_status = doctor.get("map_status")
        return {
            "hub": str(self.root),
            "query": query,
            "doctor": doctor,
            "map_status": map_status,
            "migrated": migrated,
            "status": status,
            "context": context_text,
            "hint": (
                "将 context 字段整段注入提示；同任务重复开场请复用相同 query。"
                + (
                    f" 当前 map_status={map_status}；非 aligned 时先 map-health / map upsert。"
                    if map_status and map_status != "aligned"
                    else ""
                )
            ),
        }

    def sync(
        self,
        *,
        check_only: bool = False,
        seed: bool = False,
        apply_forget: bool = False,
        agent: str = "cursor",
        max_seed: int = 40,
        project_root: Path | str | None = None,
    ) -> dict[str, object]:
        """机械同步：evolve→reindex→可选 seed/forget→map_health；语义补写仍靠 Agent。"""
        self._ensure_initialized()
        root = Path(project_root).expanduser().resolve() if project_root else self.root.parent
        companions = probe_companions(project_root=root)
        if check_only:
            health = self.map_health()
            map_status = str(health.get("map_status") or "incomplete")
            drafts = list(health.get("draft_upserts") or [])
            cleanup = self.clean(apply=False)
            return {
                "hub": str(self.root),
                "check_only": True,
                "map_status": map_status,
                "map_health": health,
                "draft_upserts": drafts,
                "maintenance_required": map_status != "aligned",
                "cleanup": cleanup,
                "evolve": None,
                "reindex": None,
                "seed": None,
                "companions": companions,
                "hint": (
                    f"map_status={map_status}（只读）。"
                    "完整机械同步：memory-hub sync；语义补写按 draft_upserts；"
                    "错误记忆：memory-hub clean --apply。"
                ),
            }

        # 规划在锁外；一把锁内批量 feedback/forget + 单次 reindex
        planned = self._evolve_plan()
        with self._write_lock():
            applied = self._evolve_apply_unlocked(
                planned,
                apply_forget=apply_forget,
                only_auto_forget=True,
            )
            reindexed = self._reindex_unlocked()
        auto_forget = sum(
            1 for item in planned if item.get("action") == "suggest_forget" and item.get("auto_forget")
        )
        evolved = {
            "hub": str(self.root),
            "apply": True,
            "apply_forget": apply_forget,
            "planned": planned,
            "applied": applied,
            "counts": {
                "planned": len(planned),
                "applied": len(applied),
                "mark_stale": sum(1 for item in planned if item["action"] == "mark_stale"),
                "confirm": sum(1 for item in planned if item["action"] == "confirm"),
                "suggest_forget": sum(1 for item in planned if item["action"] == "suggest_forget"),
                "auto_forget": auto_forget,
            },
        }
        seeded = None
        if seed:
            seeded = self.map_seed(
                agent=agent,
                dry_run=False,
                max_features=max_seed,
                project_root=root,
            )
        health = self.map_health()
        map_status = str(health.get("map_status") or "incomplete")
        drafts = list(health.get("draft_upserts") or [])
        maintenance = map_status != "aligned"
        cleanup_left = [
            item
            for item in planned
            if item.get("action") == "suggest_forget" and item.get("auto_forget")
        ]
        if apply_forget:
            cleanup_left = []
        if maintenance:
            hint = (
                f"sync 完成；map_status={map_status}，maintenance_required。"
                "按 draft_upserts[].suggested_cli 补写语义后再次 sync --check。"
            )
        else:
            hint = "sync 完成；map_status=aligned。检索索引已重建。"
        if cleanup_left and not apply_forget:
            hint += f" 另有 {len(cleanup_left)} 条错误记忆可 clean --apply / sync --apply-forget。"
        return {
            "hub": str(self.root),
            "check_only": False,
            "map_status": map_status,
            "map_health": health,
            "draft_upserts": drafts,
            "maintenance_required": maintenance,
            "cleanup": {
                "candidates": cleanup_left,
                "counts": {"candidates": len(cleanup_left)},
                "apply_forget": apply_forget,
            },
            "evolve": evolved,
            "reindex": reindexed,
            "seed": seeded,
            "companions": companions,
            "hint": hint,
        }

    def close(
        self,
        *,
        task: str,
        agent: str,
        lesson: str | None = None,
        pin_core: bool = False,
        promote_inbox: bool = True,
        do_archive: bool = False,
        check_maps: bool = True,
        evolve_maps: bool = False,
        sync_maps: bool = True,
        seed_maps: bool = False,
    ) -> dict[str, object]:
        """收尾一站式：completed → distill → 可选 archive → 默认 sync（机械维护）。"""
        status = self.update_status(task=task, agent=agent, state="completed")
        distilled = self.distill(
            task=task,
            agent=agent,
            lesson=lesson,
            promote_inbox=promote_inbox,
            pin_core=pin_core,
        )
        archived = self.archive(task) if do_archive else None
        # sync_maps 默认开；--no-check-maps 时 check_maps=False 且跳过；evolve_maps 兼容旧开关
        do_sync = bool(sync_maps and check_maps) or bool(evolve_maps)
        sync_report = self.sync(seed=seed_maps, agent=agent) if do_sync else None
        map_report = (sync_report or {}).get("map_health") if sync_report else None
        map_status = str((sync_report or {}).get("map_status") or "aligned") if sync_report else None
        draft_upserts = list((sync_report or {}).get("draft_upserts") or [])
        maintenance_required = bool(sync_report) and bool(sync_report.get("maintenance_required"))
        if maintenance_required:
            features = "、".join(
                str(item.get("feature")) for item in draft_upserts[:5] if item.get("feature")
            )
            next_step = (
                f"地图 {map_status}，须先 map upsert"
                + (f"：{features}" if features else "")
                + "；未补写前勿视为收尾完成"
            )
            status = self.update_status(task=task, agent=agent, state="completed", next_step=next_step)
            hint = (
                f"maintenance_required：map_status={map_status}。"
                "按 draft_upserts 补写后 memory-hub sync --check；未对齐前勿视为任务收尾完成。"
            )
        elif sync_report is not None:
            hint = "收尾完成；map_status=aligned（已 sync）。"
        else:
            hint = "收尾完成（已跳过地图 sync）。"
        return {
            "task": task,
            "agent": agent,
            "status": status,
            "distill": distilled,
            "archive": archived,
            "sync": sync_report,
            "map_health": map_report,
            "map_status": map_status,
            "draft_upserts": draft_upserts,
            "maintenance_required": maintenance_required,
            "evolve": (sync_report or {}).get("evolve") if sync_report else None,
            "companions": (sync_report or {}).get("companions") if sync_report else None,
            "hint": hint,
        }

    @staticmethod
    def _eligible_auto_forget(
        *,
        wrong: int,
        useful: int,
        tags: set[str],
        min_wrong: int = 2,
    ) -> bool:
        """高置信错误记忆：wrong 过线且多于 useful；可自动 forget。"""
        del tags  # 保留参数供调用方统一签名；门槛只看票数
        return wrong >= min_wrong and wrong > useful

    def _evolve_plan(self, *, min_wrong: int = 2) -> list[dict[str, object]]:
        """只读规划 evolve：地图漂移/巩固 + 全库错误记忆清理候选。"""
        planned: list[dict[str, object]] = []
        planned_forget_ids: set[str] = set()
        project_root = self.root.parent
        for item in self.list_maps(limit=500):
            memory_id = item.get("memory_id")
            feature = item.get("feature")
            missing = [str(rel) for rel in (item.get("missing_paths") or [])]
            drifted = [str(rel) for rel in (item.get("drifted_paths") or [])]
            if not missing and not drifted:
                inspected = _inspect_map_paths(
                    project_root,
                    [str(rel) for rel in (item.get("paths") or [])],
                    _normalize_path_fingerprints(item.get("path_fingerprints")),
                )
                missing = inspected["missing"]
                drifted = inspected["drifted"]
            tags = {str(tag).casefold() for tag in (item.get("tags") or [])}
            useful = int(item.get("feedback_useful") or 0)
            wrong = int(item.get("feedback_wrong") or 0)
            if (missing or drifted) and "stale" not in tags:
                reasons: list[str] = []
                if missing:
                    reasons.append("缺失：" + "、".join(missing[:5]))
                if drifted:
                    reasons.append("漂移：" + "、".join(drifted[:5]))
                reason = "；".join(reasons)
                planned.append(
                    {
                        "action": "mark_stale",
                        "feature": feature,
                        "memory_id": memory_id,
                        "missing_paths": missing,
                        "drifted_paths": drifted,
                        "reason": reason,
                        "suggested_cli": _map_upsert_cli(
                            str(feature or "feature"),
                            paths=[p for p in (item.get("paths") or []) if p not in missing][:3],
                        ),
                    }
                )
            if useful >= 3 and str(item.get("confidence") or "") in {
                "inferred",
                "tentative",
                "unspecified",
            }:
                planned.append(
                    {
                        "action": "confirm",
                        "feature": feature,
                        "memory_id": memory_id,
                        "reason": f"feedback_useful={useful}，建议巩固为 confirmed",
                    }
                )
            if memory_id and self._eligible_auto_forget(
                wrong=wrong, useful=useful, tags=tags, min_wrong=min_wrong
            ):
                mid = str(memory_id)
                planned_forget_ids.add(mid)
                planned.append(
                    {
                        "action": "suggest_forget",
                        "feature": feature,
                        "memory_id": mid,
                        "path": item.get("path"),
                        "wrong": wrong,
                        "useful": useful,
                        "auto_forget": True,
                        "reason": f"feedback_wrong={wrong} > useful={useful}；可 clean --apply",
                    }
                )
            elif memory_id and (wrong >= 1 or "disputed" in tags) and str(memory_id) not in planned_forget_ids:
                planned.append(
                    {
                        "action": "suggest_forget",
                        "feature": feature,
                        "memory_id": str(memory_id),
                        "path": item.get("path"),
                        "wrong": wrong,
                        "useful": useful,
                        "auto_forget": False,
                        "reason": f"feedback_wrong={wrong} 或 disputed；未达自动清理线（需 wrong>={min_wrong} 且 >useful）",
                    }
                )

        # 非地图记忆：踩坑/inbox 等错误投票
        docs = self._search_docs()
        for relative, doc in docs.items():
            if not isinstance(doc, dict) or doc.get("is_map"):
                continue
            collection = str(doc.get("collection") or "")
            if collection not in ACTIVE_MEMORY_COLLECTIONS:
                continue
            memory_id = doc.get("id")
            if not isinstance(memory_id, str) or not memory_id:
                continue
            if memory_id in planned_forget_ids:
                continue
            tags = {str(tag).casefold() for tag in (doc.get("tags") or [])}
            useful = int(doc.get("feedback_useful") or 0)
            wrong = int(doc.get("feedback_wrong") or 0)
            if not self._eligible_auto_forget(
                wrong=wrong, useful=useful, tags=tags, min_wrong=min_wrong
            ):
                if wrong >= 1 or "disputed" in tags:
                    planned.append(
                        {
                            "action": "suggest_forget",
                            "feature": doc.get("feature") or doc.get("title") or doc.get("key"),
                            "memory_id": memory_id,
                            "path": relative.replace("\\", "/"),
                            "wrong": wrong,
                            "useful": useful,
                            "auto_forget": False,
                            "reason": (
                                f"feedback_wrong={wrong} 或 disputed；"
                                f"未达自动清理线（需 wrong>={min_wrong} 且 >useful）"
                            ),
                        }
                    )
                continue
            planned_forget_ids.add(memory_id)
            planned.append(
                {
                    "action": "suggest_forget",
                    "feature": doc.get("feature") or doc.get("title") or doc.get("key"),
                    "memory_id": memory_id,
                    "path": relative.replace("\\", "/"),
                    "wrong": wrong,
                    "useful": useful,
                    "auto_forget": True,
                    "reason": f"feedback_wrong={wrong} > useful={useful}；可 clean --apply",
                }
            )
        return planned

    def _evolve_apply_unlocked(
        self,
        planned: Sequence[dict[str, object]],
        *,
        apply_forget: bool,
        only_auto_forget: bool = False,
    ) -> list[dict[str, object]]:
        """在已持写锁下批量执行 evolve 写操作；不重建索引。"""
        applied: list[dict[str, object]] = []
        for item in planned:
            action = str(item.get("action") or "")
            memory_id = item.get("memory_id")
            if not memory_id:
                continue
            mid = str(memory_id)
            if action == "mark_stale":
                result = self._feedback_unlocked(
                    signal="stale",
                    memory_id=mid,
                    reason=str(item.get("reason") or ""),
                )
                result.pop("collection", None)
                applied.append(result)
            elif action == "confirm":
                result = self._feedback_unlocked(
                    signal="useful",
                    memory_id=mid,
                    reason="evolve confirm",
                )
                result.pop("collection", None)
                applied.append(result)
            elif action == "suggest_forget" and apply_forget:
                if only_auto_forget and not item.get("auto_forget"):
                    continue
                result = self._forget_unlocked(memory_id=mid)
                result.pop("collection", None)
                applied.append(result)
        return applied

    def evolve(self, *, apply: bool = False, apply_forget: bool = False) -> dict[str, object]:
        """自我进化扫描：失效地图标 stale；高 useful 巩固；高 wrong 建议 forget（可选真正 forget）。"""
        self._ensure_initialized()
        planned = self._evolve_plan()
        applied: list[dict[str, object]] = []
        if apply:
            with self._write_lock():
                applied = self._evolve_apply_unlocked(
                    planned,
                    apply_forget=apply_forget,
                    only_auto_forget=True,
                )
                touched = {
                    str(Path(str(item.get("path") or item.get("from") or "")).parts[0])
                    for item in applied
                    if item.get("path") or item.get("from")
                }
                collections = tuple(name for name in touched if name in INDEXED_COLLECTIONS)
                if collections or any(item.get("from") for item in applied):
                    self._touch_index_unlocked(collections=collections)

        auto_forget = sum(1 for item in planned if item.get("action") == "suggest_forget" and item.get("auto_forget"))
        return {
            "hub": str(self.root),
            "apply": apply,
            "apply_forget": apply_forget,
            "planned": planned,
            "applied": applied,
            "counts": {
                "planned": len(planned),
                "applied": len(applied),
                "mark_stale": sum(1 for item in planned if item["action"] == "mark_stale"),
                "confirm": sum(1 for item in planned if item["action"] == "confirm"),
                "suggest_forget": sum(1 for item in planned if item["action"] == "suggest_forget"),
                "auto_forget": auto_forget,
            },
        }

    def clean(self, *, apply: bool = False, min_wrong: int = 2) -> dict[str, object]:
        """清理高置信错误记忆：默认 dry-run；--apply 将 auto_forget 项移入 archive/forgotten。"""
        self._ensure_initialized()
        if min_wrong < 1:
            raise MemoryHubError("min_wrong 必须大于 0")
        planned = [
            item
            for item in self._evolve_plan(min_wrong=min_wrong)
            if item.get("action") == "suggest_forget" and item.get("auto_forget")
        ]
        applied: list[dict[str, object]] = []
        if apply and planned:
            with self._write_lock():
                applied = self._evolve_apply_unlocked(
                    planned,
                    apply_forget=True,
                    only_auto_forget=True,
                )
                touched = {
                    str(Path(str(item.get("from") or "")).parts[0])
                    for item in applied
                    if item.get("from")
                }
                collections = tuple(name for name in touched if name in INDEXED_COLLECTIONS)
                if collections or applied:
                    self._touch_index_unlocked(collections=collections)
        return {
            "hub": str(self.root),
            "apply": apply,
            "min_wrong": min_wrong,
            "candidates": planned,
            "forgotten": applied,
            "counts": {
                "candidates": len(planned),
                "forgotten": len(applied),
            },
            "hint": (
                f"已 forget {len(applied)} 条（archive/forgotten）。"
                if apply
                else (
                    f"{len(planned)} 条可自动清理（wrong>={min_wrong} 且 >useful）。"
                    "确认后：memory-hub clean --apply"
                    if planned
                    else f"无可自动清理项（阈值：wrong>={min_wrong} 且多于 useful）。"
                )
            ),
        }

    def doctor(self) -> dict[str, object]:
        issues: list[str] = []
        warnings: list[str] = []
        map_status = "incomplete"
        if not self.root.exists():
            issues.append("记忆库目录不存在")
            return {
                "ok": False,
                "hub": str(self.root),
                "map_status": map_status,
                "companions": probe_companions(project_root=self.root.parent),
                "issues": issues,
                "warnings": warnings,
                "fixes": [
                    {
                        "id": "init",
                        "command": "memory-hub init",
                        "reason": "初始化记忆库",
                    }
                ],
            }
        for name in COLLECTIONS:
            path = self.root / name
            if not path.is_dir():
                issues.append(f"缺少目录：{name}")
        lock = self.root / ".memory-hub.lock"
        if lock.exists():
            try:
                payload = json.loads(lock.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            age = time.time() - lock.stat().st_mtime
            if lock_owner_gone(payload):
                issues.append("存在持有进程已退出的陈旧写锁")
            elif age > 120:
                issues.append("存在超过两分钟的陈旧写锁")
        markdown_count = 0
        stats: dict[str, object] | None = None
        if all((self.root / name).is_dir() for name in COLLECTIONS):
            stats = self.stats()
            markdown_count = int(stats.get("markdown_files") or 0)
            unreadable = int(stats.get("unreadable_records") or 0)
            if unreadable:
                issues.append(f"存在 {unreadable} 个无法按 UTF-8 读取的记忆正文（见 stats）")
            if stats["records"] and stats["metadata_coverage"] < 100:
                warnings.append(
                    f"部分记录缺少结构化元数据，当前覆盖率为 {stats['metadata_coverage']}%；旧文件仍可正常读取"
                )
            root_index = self.root / "INDEX.md"
            # 轻量：只比对 INDEX 与 meta/search-index 的 mtime，避免再扫一遍全库
            search_file = self._search_index_file()
            try:
                newest_meta = 0
                if root_index.is_file():
                    newest_meta = max(newest_meta, root_index.stat().st_mtime_ns)
                if search_file.is_file():
                    newest_meta = max(newest_meta, search_file.stat().st_mtime_ns)
                wiki_sample = list((self.root / "wiki").glob("*.md"))[:1]
                exp_sample = list((self.root / "experiences").glob("*.md"))[:1]
                for sample in wiki_sample + exp_sample:
                    if sample.name == "INDEX.md":
                        continue
                    if sample.stat().st_mtime_ns > newest_meta and root_index.is_file():
                        warnings.append("索引可能早于记忆正文，可运行 reindex 重建")
                        break
            except OSError:
                pass
            if not (self.root / "memory" / "LESSONS.md").exists():
                warnings.append("缺少 memory/LESSONS.md，可运行 migrate 补齐新结构")
            version = self.format_version()
            if _version_less(version, HUB_FORMAT_VERSION):
                warnings.append(
                    f"记忆库格式版本为 {version}，当前程序期望 {HUB_FORMAT_VERSION}；"
                    "请运行 memory-hub migrate（可先 --dry-run）"
                )
            if root_index.exists():
                try:
                    index_text = root_index.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    index_text = ""
                if "活动任务速览" not in index_text:
                    warnings.append("INDEX.md 缺少活动任务速览，可运行 migrate 或 reindex 升级")
            missing_distill = 0
            missing_query = 0
            for path in (self.root / "sessions").glob("*/*.md"):
                if path.name == "INDEX.md":
                    continue
                parsed = self._parse_status(path)
                state = str(parsed.get("state", "")).strip().casefold()
                if state in {"completed", "done"}:
                    soft_key = normalize_memory_key(
                        f"retrospective:{path.parent.name}:{path.stem}"
                    )
                    if self._find_by_key(soft_key) is None:
                        missing_distill += 1
                        if missing_distill <= 5:
                            warnings.append(
                                f"活动任务 {path.parent.name}/{path.stem} 已完成但未见 retrospective；"
                                "可运行 distill 收尾"
                            )
                elif state != "archived" and not str(parsed.get("query", "")).strip():
                    missing_query += 1
                    if missing_query <= 5:
                        warnings.append(
                            f"活动任务 {path.parent.name}/{path.stem} 未固定检索词；"
                            "建议 status --query 以稳定 context 前缀缓存"
                        )
            if missing_distill > 5:
                warnings.append(f"另有 {missing_distill - 5} 个已完成任务缺少 distill 回顾")
            if missing_query > 5:
                warnings.append(f"另有 {missing_query - 5} 个活动任务未固定检索词")
            # 复用 map_health，避免 doctor 再扫一遍地图 + 指纹
            health = self.map_health(limit=200)
            map_status = str(health.get("map_status") or "incomplete")
            counts = health.get("counts") if isinstance(health.get("counts"), dict) else {}
            for issue in (health.get("issues") or [])[:5]:
                feature = issue.get("feature")
                if issue.get("stale_tagged"):
                    warnings.append(
                        f"地图 {feature} 带有 stale/disputed 标记；可 map upsert 更新或 feedback useful"
                    )
                missing_paths = issue.get("missing_paths") or []
                if missing_paths:
                    sample = "、".join(str(p) for p in missing_paths[:3])
                    warnings.append(f"地图 {feature} 关联路径可能失效：{sample}；请 map upsert 修正")
                drifted_paths = issue.get("drifted_paths") or []
                if drifted_paths:
                    sample = "、".join(str(p) for p in drifted_paths[:3])
                    warnings.append(
                        f"地图 {feature} 关联路径内容已漂移：{sample}；请 map upsert 刷新指纹"
                    )
                if issue.get("needs_fingerprint"):
                    warnings.append(
                        f"地图 {feature} 尚无路径指纹；"
                        "建议 migrate --backfill-map-fingerprints 或 map upsert"
                    )
            issues_count = int(counts.get("issues") or 0)
            if issues_count > 5:
                warnings.append(f"另有 {issues_count - 5} 个地图问题，见 map-health / draft_upserts")
            if map_status != "aligned":
                warnings.append(
                    f"map_status={map_status}；运行 map-health 查看 draft_upserts 并补写"
                )
            if not search_file.is_file():
                warnings.append("缺少本地检索索引 meta/search-index.json；首次 recall/locate 会自动重建，也可 reindex")
        else:
            # 目录不齐时仍统计 md 数量（轻量）
            try:
                markdown_count = sum(1 for _ in self.root.rglob("*.md"))
            except OSError:
                markdown_count = 0
        fixes: list[dict[str, str]] = []
        warning_text = "\n".join(str(item) for item in warnings)
        issue_text = "\n".join(str(item) for item in issues)
        blob = warning_text + "\n" + issue_text
        if "migrate" in blob.casefold() or "格式版本" in blob:
            fixes.append(
                {
                    "id": "migrate",
                    "command": "memory-hub migrate",
                    "reason": "升级记忆库结构/格式",
                }
            )
        if "backfill-map-fingerprints" in blob or "尚无路径指纹" in blob or "缺少路径指纹" in blob:
            fixes.append(
                {
                    "id": "backfill-fp",
                    "command": "memory-hub migrate --backfill-map-fingerprints",
                    "reason": "补录地图路径指纹",
                }
            )
        if "reindex" in blob.casefold() or "检索索引" in blob or "索引可能早于" in blob:
            fixes.append(
                {
                    "id": "reindex",
                    "command": "memory-hub reindex",
                    "reason": "重建 Markdown INDEX 与检索索引",
                }
            )
        if "陈旧写锁" in blob:
            fixes.append(
                {
                    "id": "clear-stale-lock",
                    "command": "memory-hub doctor",
                    "reason": "确认无其它进程后删除 .memory-hub.lock 再写入",
                }
            )
        if "未固定检索词" in blob:
            fixes.append(
                {
                    "id": "pin-query",
                    "command": "memory-hub status --task <task> --agent <agent> --query \"…\"",
                    "reason": "为活动任务固定检索词以护前缀缓存",
                }
            )
        if "失效" in blob or "漂移" in blob or "stale/disputed" in blob:
            fixes.append(
                {
                    "id": "map-health",
                    "command": "memory-hub map-health",
                    "reason": "查看可执行 suggested_actions",
                }
            )
            fixes.append(
                {
                    "id": "evolve-apply",
                    "command": "memory-hub evolve --apply",
                    "reason": "将缺失/漂移地图标 stale",
                }
            )
        if "distill" in blob.casefold() or "retrospective" in blob:
            fixes.append(
                {
                    "id": "distill",
                    "command": "memory-hub distill --task <task> --agent <agent>",
                    "reason": "为已完成任务补回顾",
                }
            )
        companions = probe_companions(project_root=self.root.parent if self.root.exists() else None)
        return {
            "ok": not issues,
            "hub": str(self.root),
            "format_version": self.format_version() if self.root.exists() else None,
            "expected_format_version": HUB_FORMAT_VERSION,
            "markdown_files": markdown_count,
            "map_status": map_status,
            "companions": companions,
            "issues": issues,
            "warnings": warnings,
            "fixes": fixes,
            "stats": stats,
        }

    def distill(
        self,
        *,
        task: str,
        agent: str,
        lesson: str | None = None,
        promote_inbox: bool = True,
        pin_core: bool = False,
    ) -> dict[str, object]:
        """任务收尾：软自动总结进 experiences（key 覆盖），可选晋升 inbox、写入 LESSONS/CORE。"""
        self._ensure_initialized()
        task = safe_segment(task, "任务名")
        agent = safe_segment(agent, "代理名")
        status_path = self.root / "sessions" / task / f"{agent}.md"
        status = self._parse_status(status_path) if status_path.is_file() else {}
        objective = one_line(str(status.get("objective", ""))) or task
        completed = [str(item) for item in (status.get("completed") or [])]
        blocker = one_line(str(status.get("blocker", "")))
        next_step = one_line(str(status.get("next_step", "")))
        state = one_line(str(status.get("state", ""))) or "unknown"
        stamp = now().isoformat(timespec="seconds")
        explicit_lesson = one_line(lesson) if lesson else ""
        soft_key = normalize_memory_key(f"retrospective:{task}:{agent}")
        completed_text = "；".join(one_line(item) for item in completed) if completed else "（无）"
        draft_lesson = explicit_lesson
        if not draft_lesson and blocker and blocker not in {"无", "none", "-"}:
            draft_lesson = f"曾阻塞：{blocker}"
        narrative = (
            f"观察草稿（inferred，非硬约束；多人协作时以当前仓库与用户指令为准，可被后续 distill 覆盖）\n\n"
            f"目标：{objective}\n"
            f"状态：{state}\n"
            f"阻塞：{blocker or '无'}\n"
            f"下一步：{next_step or '无'}\n\n"
            f"已完成：{completed_text}\n\n"
            f"教训草稿：{draft_lesson or '（未单独提炼；见完成项）'}"
        )
        fingerprint = content_fingerprint(narrative)

        promoted: list[str] = []
        retrospective_path: str | None = None
        lessons_updated = False
        core_updated = False
        retrospective_updated = False
        retrospective_deduped = False

        with self._write_lock():
            existing_path = self._find_by_key(soft_key)
            if existing_path is not None:
                old_meta, _ = split_frontmatter(existing_path.read_text(encoding="utf-8"))
                if old_meta.get("content_hash") == fingerprint:
                    retrospective_path = existing_path.relative_to(self.root).as_posix()
                    retrospective_deduped = True
                else:
                    memory_id = str(old_meta.get("id") or f"mem-{uuid.uuid4().hex}")
                    created_at = str(old_meta.get("created_at") or stamp)
                    metadata = {
                        "id": memory_id,
                        "key": soft_key,
                        "type": "event",
                        "source_task": task,
                        "source_agent": agent,
                        "created_at": created_at,
                        "updated_at": stamp,
                        "confidence": "inferred",
                        "tags": ["retrospective", "auto-summary"],
                        "links": [],
                        "content_hash": fingerprint,
                    }
                    body = frontmatter(metadata) + (
                        f"# 回顾：{objective}\n\n"
                        f"- Task: {task}\n"
                        f"- Agent: {agent}\n"
                        f"- Key: {soft_key}\n\n"
                        f"{narrative}\n"
                    )
                    atomic_write(existing_path, body)
                    retrospective_path = existing_path.relative_to(self.root).as_posix()
                    retrospective_updated = True
            else:
                memory_id = f"mem-{uuid.uuid4().hex}"
                stem = f"retrospective-{slug(task)}-{slug(agent)}"
                path = self.root / "experiences" / f"{stem}.md"
                counter = 1
                while path.exists():
                    path = self.root / "experiences" / f"{stem}-{counter}.md"
                    counter += 1
                metadata = {
                    "id": memory_id,
                    "key": soft_key,
                    "type": "event",
                    "source_task": task,
                    "source_agent": agent,
                    "created_at": stamp,
                    "confidence": "inferred",
                    "tags": ["retrospective", "auto-summary"],
                    "links": [],
                    "content_hash": fingerprint,
                }
                body = frontmatter(metadata) + (
                    f"# 回顾：{objective}\n\n"
                    f"- Task: {task}\n"
                    f"- Agent: {agent}\n"
                    f"- Key: {soft_key}\n\n"
                    f"{narrative}\n"
                )
                atomic_write(path, body)
                retrospective_path = path.relative_to(self.root).as_posix()
                retrospective_updated = True

            if promote_inbox:
                inbox = self.root / "inbox"
                for candidate in list(inbox.glob("*.md")):
                    if candidate.name == "INDEX.md":
                        continue
                    try:
                        metadata, _ = split_frontmatter(candidate.read_text(encoding="utf-8"))
                    except (OSError, UnicodeDecodeError):
                        continue
                    if metadata.get("source_task") != task:
                        continue
                    destination = self.root / "experiences" / candidate.name
                    if destination.exists():
                        continue
                    shutil.move(str(candidate), str(destination))
                    promoted.append(destination.relative_to(self.root).as_posix())

            # 只有显式 --lesson 才写入 LESSONS/CORE，避免软总结变成硬引导
            if explicit_lesson:
                lessons_path = self.root / "memory" / "LESSONS.md"
                if not lessons_path.exists():
                    atomic_write(
                        lessons_path,
                        "# Lessons\n\n一行一条：短教训或「勿再犯」指针。详情见 experiences/。\n",
                    )
                existing = lessons_path.read_text(encoding="utf-8")
                bullet = f"- `{task}`: {explicit_lesson}"
                lesson_norm = explicit_lesson.casefold()
                already = bullet in existing or any(
                    lesson_norm == line.split(":", 1)[-1].strip().casefold()
                    for line in existing.splitlines()
                    if line.startswith("- ")
                )
                if not already:
                    if not existing.endswith("\n"):
                        existing += "\n"
                    atomic_write(lessons_path, existing + bullet + "\n")
                    lessons_updated = True
                if pin_core:
                    core_path = self.root / "memory" / "CORE.md"
                    if not core_path.exists():
                        atomic_write(core_path, "# Core Memory\n\n")
                    core_text = core_path.read_text(encoding="utf-8")
                    pointer = f"- 见教训 `{task}` → experiences（{explicit_lesson}）"
                    if pointer not in core_text and explicit_lesson.casefold() not in core_text.casefold():
                        if "## Distilled" not in core_text:
                            core_text = core_text.rstrip() + "\n\n## Distilled\n\n"
                        if not core_text.endswith("\n"):
                            core_text += "\n"
                        atomic_write(core_path, core_text + pointer + "\n")
                        core_updated = True

            collections: list[str] = ["experiences"]
            if promote_inbox:
                collections.append("inbox")
            self._touch_index_unlocked(collections=tuple(collections))

        return {
            "task": task,
            "agent": agent,
            "retrospective": retrospective_path,
            "key": soft_key,
            "confidence": "inferred",
            "updated": retrospective_updated,
            "deduped": retrospective_deduped,
            "promoted": promoted,
            "lesson": explicit_lesson or None,
            "lessons_updated": lessons_updated,
            "core_updated": core_updated,
        }

