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
        self.assertEqual("*\n!.gitignore\n", (self.root / ".gitignore").read_text(encoding="utf-8"))
        self.assertIn("AI Memory Hub", (self.root / "INDEX.md").read_text(encoding="utf-8"))

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
        self.assertEqual(str(self.root), payload["hub"])

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
