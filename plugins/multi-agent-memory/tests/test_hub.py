from __future__ import annotations

import json
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
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        payload = json.loads(completed.stdout)
        self.assertEqual("legacy-task", payload["task"])
        self.assertTrue(Path(payload["path"]).exists())


if __name__ == "__main__":
    unittest.main()
