from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "src"))

from multi_agent_memory.hub import MemoryHub, MemoryHubError


class MemoryHubTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / ".ai-memory-hub"
        self.hub = MemoryHub(self.root)
        self.hub.init()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_init_creates_private_markdown_structure(self) -> None:
        self.assertTrue((self.root / "memory" / "CORE.md").exists())
        self.assertTrue((self.root / "memory" / "LESSONS.md").exists())
        self.assertEqual("*\n!.gitignore\n", (self.root / ".gitignore").read_text(encoding="utf-8"))
        self.assertIn("AI Memory Hub", (self.root / "INDEX.md").read_text(encoding="utf-8"))
        self.assertEqual("0.7.0", (self.root / "VERSION").read_text(encoding="utf-8").strip())

    def test_migrate_upgrades_legacy_hub_structure(self) -> None:
        legacy_root = Path(self.temp.name) / "legacy-hub"
        for name in ("memory", "sessions", "experiences", "wiki", "inbox", "archive"):
            (legacy_root / name).mkdir(parents=True)
        (legacy_root / "memory" / "CORE.md").write_text("# Core Memory\n\nold\n", encoding="utf-8")
        (legacy_root / "memory" / "USER.md").write_text("# User Memory\n\n", encoding="utf-8")
        (legacy_root / "memory" / "AGENTS.md").write_text("# Agent Memory\n\n", encoding="utf-8")
        inbox = legacy_root / "inbox" / "note.md"
        inbox.write_text(
            '---\nid: "mem-legacy"\ntype: "note"\ntags: ["auth"]\n---\n\n# old note\n\nbody\n',
            encoding="utf-8",
        )
        hub = MemoryHub(legacy_root)
        report = hub.doctor()
        self.assertTrue(any("migrate" in warning for warning in report["warnings"]))
        dry = hub.migrate(dry_run=True, backfill_hash=True)
        self.assertTrue(dry["dry_run"])
        self.assertTrue(any(item.startswith("create-file:memory/LESSONS.md") for item in dry["planned"]))
        result = hub.migrate(backfill_hash=True)
        self.assertFalse(result["dry_run"])
        self.assertTrue((legacy_root / "memory" / "LESSONS.md").exists())
        self.assertEqual("0.7.0", (legacy_root / "VERSION").read_text(encoding="utf-8").strip())
        self.assertIn("活动任务速览", (legacy_root / "INDEX.md").read_text(encoding="utf-8"))
        self.assertIn("inbox/note.md", result["hashed"])
        meta, _ = __import__("multi_agent_memory.hub", fromlist=["_split_frontmatter"])._split_frontmatter(
            inbox.read_text(encoding="utf-8")
        )
        self.assertTrue(str(meta.get("content_hash")))
        # existing CORE body preserved
        self.assertIn("old", (legacy_root / "memory" / "CORE.md").read_text(encoding="utf-8"))
        again = hub.migrate(backfill_hash=True)
        self.assertEqual([], again["hashed"])

    def test_status_accepts_legacy_fields_and_preserves_omitted_values(self) -> None:
        self.hub.update_status(
            task="feature-a",
            agent="codex",
            objective="实现功能 A",
            state="in-progress",
            completed=["完成分析", "补充测试"],
            next_step="运行构建",
            blocker="无",
        )
        result = self.hub.update_status(task="feature-a", agent="codex", state="completed")
        content = Path(result["path"]).read_text(encoding="utf-8")
        self.assertIn("- 目标：实现功能 A", content)
        self.assertIn("- 已完成：完成分析；补充测试", content)
        self.assertIn("- 当前状态：completed", content)

    def test_status_append_completed_merges_without_replacing(self) -> None:
        self.hub.update_status(
            task="feature-a",
            agent="cursor",
            objective="实现功能 A",
            completed=["完成分析"],
        )
        result = self.hub.update_status(
            task="feature-a",
            agent="cursor",
            completed=["补充测试"],
            append_completed=True,
        )
        self.assertEqual(["完成分析", "补充测试"], result["completed"])

    def test_get_status_reads_without_writing(self) -> None:
        self.hub.update_status(task="feature-a", agent="cursor", objective="实现功能 A", state="in-progress")
        shown = self.hub.get_status(task="feature-a", agent="cursor")
        self.assertEqual("实现功能 A", shown["objective"])
        self.assertEqual("in-progress", shown["state"])

    def test_resolve_hub_walks_parents_for_default_name(self) -> None:
        from multi_agent_memory.hub import resolve_hub

        nested = Path(self.temp.name) / "apps" / "web"
        nested.mkdir(parents=True)
        found = resolve_hub(start=nested)
        self.assertEqual(self.root.resolve(), found)

    def test_promote_moves_inbox_memory_to_experiences(self) -> None:
        remembered = self.hub.remember(
            agent="cursor",
            text="刷新请求必须共用单例 Promise",
            memory_type="decision",
        )
        result = self.hub.promote(to="experiences", memory_id=str(remembered["id"]))
        self.assertEqual("experiences", result["collection"])
        self.assertFalse(Path(remembered["path"]).exists())
        self.assertTrue((self.root / result["to"]).is_file())

    def test_context_full_includes_memory_body(self) -> None:
        self.hub.remember(
            agent="cursor",
            text="认证刷新必须复用同一个任务且附带详细约束说明段落",
            memory_type="decision",
        )
        summary = self.hub.context("认证刷新", max_chars=20_000)
        full = self.hub.context("认证刷新", max_chars=20_000, full=True)
        self.assertIn("认证刷新必须复用同一个任务", full)
        self.assertGreaterEqual(len(full), len(summary))

    def test_overview_and_list_expose_active_work(self) -> None:
        self.hub.update_status(task="auth", agent="cursor", objective="修认证", state="in-progress")
        self.hub.remember(agent="cursor", text="认证刷新采用单例任务", memory_type="decision", tags=["auth"])
        overview = self.hub.overview()
        self.assertEqual(1, overview["counts"]["sessions"])
        self.assertEqual(1, len(overview["active_tasks"]))
        self.assertIn("修认证", overview["active_tasks"][0]["objective"])
        listed = self.hub.list_entries("inbox", memory_type="decision", tag="auth")
        self.assertEqual(1, len(listed))
        index = (self.root / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("活动任务速览", index)
        self.assertIn("修认证", index)

    def test_remember_dedupes_identical_content(self) -> None:
        first = self.hub.remember(agent="cursor", text="同一条决策正文")
        second = self.hub.remember(agent="claude", text="同一条决策正文")
        self.assertTrue(second["deduped"])
        self.assertEqual(first["id"], second["id"])
        notes = [path for path in (self.root / "inbox").glob("*.md") if path.name != "INDEX.md"]
        self.assertEqual(1, len(notes))

    def test_remember_updates_by_stable_key(self) -> None:
        first = self.hub.remember(
            agent="cursor",
            text="HubLock 用文件锁",
            key="feature:hub-lock",
            tags=["map"],
            memory_type="fact",
        )
        second = self.hub.remember(
            agent="cursor",
            text="HubLock 用文件锁 + 同进程线程锁",
            key="feature:hub-lock",
            tags=["map", "concurrency"],
            memory_type="fact",
        )
        self.assertTrue(second["updated"])
        self.assertFalse(second["deduped"])
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["path"], second["path"])
        notes = [path for path in (self.root / "inbox").glob("*.md") if path.name != "INDEX.md"]
        self.assertEqual(1, len(notes))
        body = notes[0].read_text(encoding="utf-8")
        self.assertIn("同进程线程锁", body)
        self.assertIn("concurrency", body)

    def test_remember_key_update_wins_over_unrelated_duplicate_text(self) -> None:
        other = self.hub.remember(agent="cursor", text="共享正文内容")
        keyed = self.hub.remember(
            agent="cursor",
            text="旧版说明",
            key="feature:shared-doc",
        )
        updated = self.hub.remember(
            agent="cursor",
            text="共享正文内容",
            key="feature:shared-doc",
        )
        self.assertTrue(updated["updated"])
        self.assertEqual(keyed["id"], updated["id"])
        self.assertNotEqual(other["id"], updated["id"])
        self.assertIn("共享正文内容", Path(updated["path"]).read_text(encoding="utf-8"))

    def test_forget_moves_to_archive_forgotten(self) -> None:
        remembered = self.hub.remember(agent="cursor", text="过时的临时结论", memory_type="note")
        result = self.hub.forget(memory_id=str(remembered["id"]))
        self.assertTrue(result["to"].startswith("archive/forgotten/"))
        self.assertFalse(Path(remembered["path"]).exists())
        self.assertEqual([], self.hub.recall("过时的临时结论"))
        found = self.hub.recall("过时的临时结论", include_forgotten=True)
        self.assertTrue(found)

    def test_recall_filters_and_relation_boost(self) -> None:
        first = self.hub.remember(
            agent="cursor",
            text="认证客户端约定",
            memory_type="decision",
            tags=["auth"],
        )
        self.hub.remember(
            agent="cursor",
            text="认证刷新请求必须复用单例",
            memory_type="decision",
            tags=["auth"],
            links=[("requires", str(first["id"]))],
        )
        filtered = self.hub.recall("刷新", memory_type="decision", tag="auth")
        self.assertTrue(filtered)
        boosted = self.hub.recall("认证", memory_type="decision")
        by_id = {item.memory_id: item for item in boosted}
        self.assertIn(first["id"], by_id)
        self.assertIn("关系链接加分", by_id[first["id"]].reason)

    def test_dead_lock_owner_is_reclaimed(self) -> None:
        lock = self.root / ".memory-hub.lock"
        lock.write_text(
            json.dumps({"pid": 999_999_999, "host": "same-host-will-check", "created": 1}, ensure_ascii=False),
            encoding="utf-8",
        )
        # Force same-host reclaim path by rewriting host after import of helper behavior:
        import socket

        lock.write_text(
            json.dumps({"pid": 999_999_999, "host": socket.gethostname(), "created": 1}, ensure_ascii=False),
            encoding="utf-8",
        )
        self.hub.remember(agent="cursor", text="写锁回收后仍可写入")
        self.assertFalse(lock.exists())

    def test_task_name_cannot_escape_hub(self) -> None:
        with self.assertRaises(MemoryHubError):
            self.hub.update_status(task="../outside", agent="codex")

    def test_remember_recall_and_context(self) -> None:
        self.hub.remember(agent="codex", text="车型比较结果需要生成分享图片", tags=["vehicle", "share"])
        results = self.hub.recall("车型 分享", limit=5)
        self.assertTrue(results)
        self.assertIn("inbox/", results[0].path)
        context = self.hub.context("车型")
        self.assertIn("Core Memory", context)
        self.assertIn("车型比较", context)

    def test_remember_writes_traceable_frontmatter(self) -> None:
        result = self.hub.remember(
            agent="codex",
            text="刷新令牌请求必须复用同一个任务",
            tags=["auth", "concurrency"],
            memory_type="decision",
            source_task="auth-refresh",
            confidence="confirmed",
            links=[("requires", "mem-auth-client")],
        )

        content = Path(result["path"]).read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---\n"))
        self.assertIn('type: "decision"', content)
        self.assertIn('source_task: "auth-refresh"', content)
        self.assertIn('source_agent: "codex"', content)
        self.assertIn('confidence: "confirmed"', content)
        self.assertIn('"relation": "requires"', content)
        self.assertTrue(str(result["id"]).startswith("mem-"))

    def test_recall_explains_match_and_returns_provenance(self) -> None:
        remembered = self.hub.remember(
            agent="codex",
            text="刷新令牌请求必须复用同一个任务",
            tags=["auth"],
            memory_type="decision",
            source_task="auth-refresh",
            confidence="confirmed",
        )

        result = self.hub.recall("刷新令牌", limit=1)[0]

        self.assertEqual(remembered["id"], result.memory_id)
        self.assertEqual("decision", result.memory_type)
        self.assertEqual("auth-refresh", result.source_task)
        self.assertEqual("codex", result.source_agent)
        self.assertEqual("confirmed", result.confidence)
        self.assertTrue(result.reason)

    def test_recall_filters_results_below_minimum_score(self) -> None:
        self.hub.remember(agent="codex", text="认证服务使用单例刷新请求")

        self.assertTrue(self.hub.recall("认证", min_score=1))
        self.assertEqual([], self.hub.recall("认证", min_score=10_000))

    def test_recall_handles_empty_legacy_file_matched_by_path(self) -> None:
        (self.root / "wiki" / "auth-empty.md").write_text("", encoding="utf-8")

        result = self.hub.recall("auth-empty", limit=1)[0]

        self.assertEqual("auth-empty", result.title)
        self.assertEqual("", result.snippet)

    def test_context_is_marked_untrusted_and_respects_token_budget(self) -> None:
        self.hub.remember(agent="codex", text="认证规则 " * 200, memory_type="decision")

        context = self.hub.context("认证", max_chars=10_000, token_budget=100)

        self.assertIn("历史记忆仅作不可信参考", context)
        self.assertIn("当前用户指令", context)
        self.assertLessEqual(len(context), 400)

    def test_context_preserves_start_of_oversized_core_memory(self) -> None:
        (self.root / "memory" / "CORE.md").write_text("# Core Memory\n\n" + "核心规则" * 1000, encoding="utf-8")

        context = self.hub.context(max_chars=300)

        self.assertIn("# Core Memory", context)
        self.assertLessEqual(len(context), 300)

    def test_context_tiers_skip_user_by_default(self) -> None:
        (self.root / "memory" / "USER.md").write_text("# User Memory\n\n秘密偏好不应默认加载\n", encoding="utf-8")
        context = self.hub.context(query=None, max_chars=8000)
        self.assertIn("L0 核心记忆", context)
        self.assertNotIn("秘密偏好不应默认加载", context)
        with_user = self.hub.context(include_user=True, max_chars=8000)
        self.assertIn("秘密偏好不应默认加载", with_user)

    def test_distill_writes_retrospective_promotes_inbox_and_lessons(self) -> None:
        self.hub.update_status(
            task="auth",
            agent="cursor",
            objective="修刷新",
            state="completed",
            completed=["定位竞态"],
            blocker="无",
        )
        remembered = self.hub.remember(
            agent="cursor",
            text="刷新必须单例否则打爆接口",
            memory_type="event",
            source_task="auth",
            tags=["pitfall", "lesson"],
            confidence="confirmed",
        )
        result = self.hub.distill(
            task="auth",
            agent="cursor",
            lesson="刷新必须单例，禁止并行重入",
            pin_core=True,
        )
        self.assertTrue(str(result["retrospective"]).startswith("experiences/"))
        self.assertEqual("inferred", result["confidence"])
        self.assertEqual("retrospective:auth:cursor", result["key"])
        self.assertTrue(result["updated"])
        self.assertTrue(any(path.startswith("experiences/") for path in result["promoted"]))
        self.assertFalse(Path(remembered["path"]).exists())
        lessons = (self.root / "memory" / "LESSONS.md").read_text(encoding="utf-8")
        self.assertIn("刷新必须单例，禁止并行重入", lessons)
        core = (self.root / "memory" / "CORE.md").read_text(encoding="utf-8")
        self.assertIn("## Distilled", core)
        self.assertIn("`auth`", core)
        meta, body = __import__("multi_agent_memory.hub", fromlist=["_split_frontmatter"])._split_frontmatter(
            (self.root / result["retrospective"]).read_text(encoding="utf-8")
        )
        self.assertEqual("inferred", meta.get("confidence"))
        self.assertIn("auto-summary", meta.get("tags", []))
        self.assertIn("观察草稿", body)

    def test_distill_soft_summary_upserts_without_touching_lessons(self) -> None:
        self.hub.update_status(
            task="cache-task",
            agent="cursor",
            objective="稳缓存",
            state="completed",
            completed=["初版"],
        )
        first = self.hub.distill(task="cache-task", agent="cursor")
        self.assertTrue(first["updated"])
        self.assertFalse(first["lessons_updated"])
        lessons_before = (self.root / "memory" / "LESSONS.md").read_text(encoding="utf-8")
        self.hub.update_status(
            task="cache-task",
            agent="cursor",
            completed=["初版", "再 distill"],
            append_completed=False,
        )
        second = self.hub.distill(task="cache-task", agent="cursor")
        self.assertTrue(second["updated"])
        self.assertEqual(first["retrospective"], second["retrospective"])
        self.assertEqual(first["key"], second["key"])
        body = (self.root / second["retrospective"]).read_text(encoding="utf-8")
        self.assertIn("再 distill", body)
        self.assertEqual(lessons_before, (self.root / "memory" / "LESSONS.md").read_text(encoding="utf-8"))
        third = self.hub.distill(task="cache-task", agent="cursor")
        self.assertTrue(third["deduped"])

    def test_context_l2_order_is_stable_by_key(self) -> None:
        zebra = self.hub.remember(
            agent="cursor",
            text="zebra 主题说明很长以便召回",
            key="feature:zebra",
            memory_type="fact",
        )
        alpha = self.hub.remember(
            agent="cursor",
            text="alpha 主题说明很长以便召回",
            key="feature:alpha",
            memory_type="fact",
        )
        self.hub.promote(to="experiences", memory_id=str(zebra["id"]))
        self.hub.promote(to="experiences", memory_id=str(alpha["id"]))
        first = self.hub.context(query="主题说明", max_chars=12000)
        second = self.hub.context(query="主题说明", max_chars=12000)
        self.assertEqual(first, second)
        alpha_at = first.find("feature:alpha")
        zebra_at = first.find("feature:zebra")
        self.assertGreater(alpha_at, 0)
        self.assertGreater(zebra_at, 0)
        self.assertLess(alpha_at, zebra_at)
        self.assertIn("L0.5 功能地图", first)
        self.assertNotIn("分数：", first)
        self.assertNotIn("高置信度加分", first)

    def test_context_stays_stable_after_feedback(self) -> None:
        mapped = self.hub.upsert_map(
            agent="cursor",
            feature="cache-prefix",
            role="前缀缓存友好地图",
            paths=["plugins/multi-agent-memory/src/multi_agent_memory/hub.py"],
            note="稳定装配",
        )
        before = self.hub.context(query="前缀缓存", max_chars=8000)
        self.hub.feedback(signal="useful", memory_id=str(mapped["id"]))
        self.hub.feedback(signal="useful", memory_id=str(mapped["id"]))
        after = self.hub.context(query="前缀缓存", max_chars=8000)
        self.assertEqual(before, after)
        self.assertIn("L0.5 功能地图", before)
        self.assertIn("cache-prefix", before)

    def test_status_pins_query_for_cache(self) -> None:
        result = self.hub.update_status(
            task="opt-task",
            agent="cursor",
            objective="优化缓存",
            query="memory-hub context",
        )
        self.assertEqual("memory-hub context", result["query"])
        shown = self.hub.get_status(task="opt-task", agent="cursor")
        self.assertEqual("memory-hub context", shown["query"])
        content = Path(result["path"]).read_text(encoding="utf-8")
        self.assertIn("- 检索词：memory-hub context", content)

    def test_context_skips_auto_summary_by_default(self) -> None:
        self.hub.update_status(task="sum-task", agent="cursor", objective="总结", state="completed", completed=["ok"])
        distilled = self.hub.distill(task="sum-task", agent="cursor")
        path = str(distilled["retrospective"]).replace("\\", "/")
        default_ctx = self.hub.context(query="总结", max_chars=8000, include_maps=False)
        self.assertNotIn(path, default_ctx)
        with_inferred = self.hub.context(
            query="总结",
            max_chars=8000,
            include_maps=False,
            include_inferred=True,
        )
        self.assertIn(path, with_inferred)

    def test_doctor_warns_about_missing_map_paths(self) -> None:
        self.hub.upsert_map(
            agent="cursor",
            feature="broken-map",
            role="失效路径",
            paths=["does/not/exist/anywhere.py"],
        )
        report = self.hub.doctor()
        self.assertTrue(report["ok"])
        self.assertTrue(any("broken-map" in warning and "失效" in warning for warning in report["warnings"]))

    def test_map_list_is_stable_by_key(self) -> None:
        self.hub.upsert_map(agent="cursor", feature="zeta", role="z", paths=["README.md"])
        self.hub.upsert_map(agent="cursor", feature="alpha", role="a", paths=["LICENSE"])
        listed = self.hub.list_maps()
        features = [item["feature"] for item in listed]
        self.assertEqual(["alpha", "zeta"], features)

    def test_orient_close_and_evolve_lifecycle(self) -> None:
        opened = self.hub.orient(
            task="life",
            agent="cursor",
            query="lifecycle-cache",
            objective="打通开场收尾",
        )
        self.assertEqual("lifecycle-cache", opened["query"])
        self.assertIn("共享记忆上下文", opened["context"])
        self.assertIn("L1 当前任务", opened["context"])
        self.assertEqual("lifecycle-cache", opened["status"]["query"])

        self.hub.upsert_map(
            agent="cursor",
            feature="ghost",
            role="失效",
            paths=["no/such/file.py"],
        )
        plan = self.hub.evolve(apply=False)
        self.assertTrue(any(item["action"] == "mark_stale" and item["feature"] == "ghost" for item in plan["planned"]))
        applied = self.hub.evolve(apply=True)
        self.assertGreaterEqual(applied["counts"]["applied"], 1)
        maps = {item["feature"]: item for item in self.hub.list_maps()}
        self.assertIn("stale", {tag.casefold() for tag in maps["ghost"]["tags"]})

        located = self.hub.locate("ghost")
        self.assertTrue(located)
        self.assertIn("no/such/file.py", located[0]["missing_paths"])

        closed = self.hub.close(task="life", agent="cursor", lesson="开场用 orient，收尾用 close")
        self.assertEqual("completed", closed["status"]["state"])
        self.assertTrue(closed["distill"]["lessons_updated"])
        self.assertIsNone(closed["archive"])

    def test_context_session_trailer_does_not_reorder_prefix(self) -> None:
        self.hub.upsert_map(
            agent="cursor",
            feature="prefix-stable",
            role="前缀",
            paths=["README.md"],
        )
        self.hub.update_status(task="trail", agent="cursor", objective="尾部", query="prefix-stable")
        first = self.hub.context(query="prefix-stable", max_chars=6000)
        second = self.hub.context(
            query="prefix-stable",
            max_chars=6000,
            session_task="trail",
            session_agent="cursor",
        )
        # 有 L1 时正文更长，但 L0/L0.5 前缀应保持一致
        cut = first.find("## L0.5") if "## L0.5" in first else len(first)
        self.assertTrue(second.startswith(first[:cut]))
        self.assertIn("L1 当前任务", second)
        self.assertGreater(second.find("L1 当前任务"), second.find("L0.5 功能地图"))

    def test_stats_reports_metadata_coverage_types_and_relations(self) -> None:
        self.hub.remember(
            agent="codex",
            text="认证刷新采用单例任务",
            memory_type="decision",
            links=[("requires", "mem-auth-client")],
        )
        (self.root / "wiki" / "legacy.md").write_text("# 旧版认证说明\n", encoding="utf-8")

        stats = self.hub.stats()

        self.assertEqual(2, stats["records"])
        self.assertEqual(1, stats["metadata_records"])
        self.assertEqual(50.0, stats["metadata_coverage"])
        self.assertEqual({"decision": 1, "legacy": 1}, stats["by_type"])
        self.assertEqual(1, stats["relations"])
        self.assertEqual(1, stats["by_collection"]["inbox"])
        self.assertEqual(1, stats["by_collection"]["wiki"])

    def test_doctor_warns_about_legacy_metadata_without_failing(self) -> None:
        (self.root / "wiki" / "legacy.md").write_text("# 旧版说明\n", encoding="utf-8")

        report = self.hub.doctor()

        self.assertTrue(report["ok"])
        self.assertEqual(0.0, report["stats"]["metadata_coverage"])
        self.assertTrue(any("结构化元数据" in warning for warning in report["warnings"]))

    def test_tokenize_query_splits_cjk_bigrams_and_latin(self) -> None:
        from multi_agent_memory.hub import _tokenize_query

        self.assertEqual(["认证", "证刷", "刷新"], _tokenize_query("认证刷新"))
        self.assertEqual(["auth", "刷新"], _tokenize_query("auth刷新"))
        self.assertEqual(["车型", "分享"], _tokenize_query("车型 分享"))

    def test_recall_matches_cjk_without_spaces(self) -> None:
        self.hub.remember(
            agent="cursor",
            text="认证服务必须复用单例刷新请求，禁止并行重入",
            memory_type="decision",
            confidence="confirmed",
        )
        # 无空格查询：旧版整词匹配会失败，二元组应命中「认证」「刷新」
        results = self.hub.recall("认证刷新", limit=5)
        self.assertTrue(results)
        self.assertIn("认证", results[0].snippet or results[0].title)
        self.assertIn("高置信度加分", results[0].reason)

    def test_recall_confidence_prefers_confirmed_over_inferred(self) -> None:
        self.hub.remember(
            agent="cursor",
            text="缓存键必须包含租户 ID",
            memory_type="decision",
            confidence="inferred",
            key="cache:tenant-inferred",
        )
        confirmed = self.hub.remember(
            agent="cursor",
            text="缓存键必须包含租户 ID 且经确认",
            memory_type="decision",
            confidence="confirmed",
            key="cache:tenant-confirmed",
        )
        ranked = self.hub.recall("缓存键 租户", limit=5)
        self.assertGreaterEqual(len(ranked), 2)
        self.assertEqual(confirmed["id"], ranked[0].memory_id)
        self.assertIn("高置信度加分", ranked[0].reason)
        inferred = next(item for item in ranked if item.key == "cache:tenant-inferred")
        self.assertIn("推断性降权", inferred.reason)
        self.assertGreater(ranked[0].score, inferred.score)

    def test_remember_touches_only_inbox_index(self) -> None:
        wiki_index = self.root / "wiki" / "INDEX.md"
        experiences_index = self.root / "experiences" / "INDEX.md"
        before_wiki = wiki_index.read_text(encoding="utf-8")
        before_exp = experiences_index.read_text(encoding="utf-8")
        wiki_mtime = wiki_index.stat().st_mtime_ns
        exp_mtime = experiences_index.stat().st_mtime_ns

        self.hub.remember(agent="cursor", text="仅应刷新 inbox 索引")

        self.assertEqual(before_wiki, wiki_index.read_text(encoding="utf-8"))
        self.assertEqual(before_exp, experiences_index.read_text(encoding="utf-8"))
        self.assertEqual(wiki_mtime, wiki_index.stat().st_mtime_ns)
        self.assertEqual(exp_mtime, experiences_index.stat().st_mtime_ns)
        inbox_index = (self.root / "inbox" / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("仅应刷新-inbox-索引", inbox_index)
        self.assertRegex((self.root / "INDEX.md").read_text(encoding="utf-8"), r"inbox/INDEX\.md\): 1 entries")

    def test_doctor_warns_when_completed_task_missing_distill(self) -> None:
        self.hub.update_status(
            task="orphan-done",
            agent="cursor",
            objective="已完成未 distill",
            state="completed",
        )
        report = self.hub.doctor()
        self.assertTrue(report["ok"])
        self.assertTrue(any("orphan-done/cursor" in warning and "distill" in warning for warning in report["warnings"]))

    def test_map_upsert_and_locate_return_short_paths(self) -> None:
        first = self.hub.upsert_map(
            agent="cursor",
            feature="auth-refresh",
            role="登录态刷新",
            paths=["src/auth/refresh.ts"],
            commands=["npm test -- auth"],
            note="单例 Promise",
        )
        self.assertTrue(str(first["path"]).replace("\\", "/").endswith(".md"))
        self.assertIn("wiki", str(first["path"]).replace("\\", "/"))
        self.assertEqual("feature:auth-refresh", first["key"])
        self.assertEqual(["src/auth/refresh.ts"], first["paths"])

        second = self.hub.upsert_map(
            agent="cursor",
            feature="auth-refresh",
            paths=["src/auth/client.ts"],
            role="登录态刷新与客户端",
        )
        self.assertTrue(second["updated"])
        self.assertEqual(
            ["src/auth/refresh.ts", "src/auth/client.ts"],
            second["paths"],
        )

        by_feature = self.hub.locate("认证刷新")
        self.assertTrue(by_feature)
        self.assertEqual("auth-refresh", by_feature[0]["feature"])
        self.assertIn("src/auth/client.ts", by_feature[0]["paths"])

        by_path = self.hub.locate("src/auth/refresh.ts")
        self.assertTrue(by_path)
        self.assertEqual(first["id"], by_path[0]["memory_id"])

    def test_feedback_useful_promotes_confidence(self) -> None:
        remembered = self.hub.remember(
            agent="cursor",
            text="地图命中后应优先打开关联路径",
            confidence="inferred",
            memory_type="fact",
        )
        once = self.hub.feedback(signal="useful", memory_id=str(remembered["id"]))
        self.assertEqual(1, once["feedback_useful"])
        self.assertEqual("inferred", once["confidence"])
        twice = self.hub.feedback(signal="useful", memory_id=str(remembered["id"]))
        self.assertEqual(2, twice["feedback_useful"])
        self.assertEqual("confirmed", twice["confidence"])

        mapped = self.hub.upsert_map(
            agent="cursor",
            feature="locate-loop",
            role="定位闭环",
            paths=["plugins/multi-agent-memory/src/multi_agent_memory/hub.py"],
        )
        stale = self.hub.feedback(signal="stale", memory_id=str(mapped["id"]))
        self.assertEqual("tentative", stale["confidence"])
        self.assertIn("stale", stale["tags"])

    def test_cli_map_locate_and_feedback(self) -> None:
        from multi_agent_memory.cli import run

        code = run(
            [
                "--hub",
                str(self.root),
                "map",
                "upsert",
                "--agent",
                "cursor",
                "--feature",
                "cli-map",
                "--role",
                "CLI 地图",
                "--path",
                "plugins/multi-agent-memory/src/multi_agent_memory/cli.py",
            ]
        )
        self.assertEqual(0, code)
        code = run(["--hub", str(self.root), "--json", "locate", "--query", "cli-map"])
        self.assertEqual(0, code)

    def test_archive_moves_task_and_reindexes(self) -> None:
        self.hub.update_status(task="done-task", agent="codex", objective="完成任务", state="completed")
        result = self.hub.archive("done-task")
        self.assertFalse((self.root / "sessions" / "done-task").exists())
        self.assertTrue(Path(result["to"]).is_dir())
        self.assertIn("done-task/codex", (self.root / "sessions" / "INDEX.md").read_text(encoding="utf-8"))

    def test_concurrent_writes_do_not_overwrite_each_other(self) -> None:
        def write(index: int) -> str:
            result = self.hub.remember(agent="codex", text=f"并发记忆 {index}", tags=["concurrency"])
            return result["path"]

        with ThreadPoolExecutor(max_workers=8) as executor:
            paths = list(executor.map(write, range(20)))
        self.assertEqual(20, len(set(paths)))
        notes = [path for path in (self.root / "inbox").glob("*.md") if path.name != "INDEX.md"]
        self.assertEqual(20, len(notes))
        self.assertTrue(self.hub.doctor()["ok"])

    def test_cli_legacy_command_and_json_output(self) -> None:
        script = PLUGIN_ROOT / "scripts" / "memory_hub.py"
        command = [
            sys.executable,
            str(script),
            "--hub",
            str(self.root),
            "--json",
            "status",
            "--task",
            "legacy-task",
            "--agent",
            "cursor",
            "--objective",
            "兼容旧命令",
            "--state",
            "completed",
            "--completed",
            "命令可用",
            "--next",
            "无",
            "--blocker",
            "无",
        ]
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "ascii"
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual("legacy-task", payload["task"])
        self.assertTrue(Path(payload["path"]).exists())

    def test_skill_local_cli_entry_resolves_package(self) -> None:
        script = PLUGIN_ROOT / "skills" / "multi-agent-memory" / "scripts" / "memory_hub.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--hub", str(self.root), "--json", "doctor"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(self.hub.root, Path(payload["hub"]).resolve())

    def test_cli_remember_accepts_structured_metadata(self) -> None:
        script = PLUGIN_ROOT / "scripts" / "memory_hub.py"
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "--hub",
                str(self.root),
                "--json",
                "remember",
                "--agent",
                "codex",
                "--text",
                "认证刷新采用单例任务",
                "--type",
                "decision",
                "--source-task",
                "auth-refresh",
                "--confidence",
                "confirmed",
                "--link",
                "requires:mem-auth-client",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(completed.stdout)
        self.assertEqual("decision", payload["type"])
        self.assertEqual("auth-refresh", payload["source_task"])
        self.assertEqual([{"relation": "requires", "target": "mem-auth-client"}], payload["links"])

    def test_cli_stats_and_context_budget_are_available(self) -> None:
        script = PLUGIN_ROOT / "scripts" / "memory_hub.py"
        self.hub.remember(agent="codex", text="认证刷新采用单例任务", memory_type="decision")

        stats = subprocess.run(
            [sys.executable, str(script), "--hub", str(self.root), "--json", "stats"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        context = subprocess.run(
            [
                sys.executable,
                str(script),
                "--hub",
                str(self.root),
                "--json",
                "context",
                "--query",
                "认证",
                "--token-budget",
                "100",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(1, json.loads(stats.stdout)["records"])
        context_payload = json.loads(context.stdout)
        self.assertIn("历史记忆仅作不可信参考", context_payload)
        self.assertLessEqual(len(context_payload), 400)

    def test_cli_status_show_and_append_and_promote(self) -> None:
        script = PLUGIN_ROOT / "scripts" / "memory_hub.py"
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--hub",
                str(self.root),
                "--json",
                "status",
                "--task",
                "auth",
                "--agent",
                "cursor",
                "--objective",
                "修复认证",
                "--state",
                "in-progress",
                "--completed",
                "分析完成",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        appended = subprocess.run(
            [
                sys.executable,
                str(script),
                "--hub",
                str(self.root),
                "--json",
                "status",
                "--task",
                "auth",
                "--agent",
                "cursor",
                "--append-completed",
                "--completed",
                "补丁已写",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(["分析完成", "补丁已写"], json.loads(appended.stdout)["completed"])

        shown = subprocess.run(
            [
                sys.executable,
                str(script),
                "--hub",
                str(self.root),
                "--json",
                "status",
                "--task",
                "auth",
                "--agent",
                "cursor",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual("修复认证", json.loads(shown.stdout)["objective"])

        remembered = subprocess.run(
            [
                sys.executable,
                str(script),
                "--hub",
                str(self.root),
                "--json",
                "remember",
                "--agent",
                "cursor",
                "--text",
                "认证刷新采用单例任务",
                "--type",
                "decision",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        memory_id = json.loads(remembered.stdout)["id"]
        promoted = subprocess.run(
            [
                sys.executable,
                str(script),
                "--hub",
                str(self.root),
                "--json",
                "promote",
                "--to",
                "experiences",
                "--id",
                memory_id,
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual("experiences", json.loads(promoted.stdout)["collection"])


if __name__ == "__main__":
    unittest.main()
