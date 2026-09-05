"""场景评测：触发词、上下文稳定性、locate 命中。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "src"))

from multi_agent_memory.hub import MemoryHub


class ScenarioEvals(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / ".ai-memory-hub"
        self.hub = MemoryHub(self.root)
        self.hub.init()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_skill_description_has_dense_triggers(self) -> None:
        text = (PLUGIN_ROOT / "skills" / "multi-agent-memory" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("description:", text)
        for needle in (
            "orient",
            "close",
            "locate",
            ".ai-memory-hub",
            "shared memory",
            "勿再犯",
            "前缀缓存",
        ):
            self.assertIn(needle, text)

    def test_context_stable_for_same_query(self) -> None:
        self.hub.upsert_map(
            agent="cursor",
            feature="auth-refresh",
            role="登录态刷新",
            paths=["src/auth/refresh.ts"],
        )
        self.hub.remember(
            agent="cursor",
            text="刷新必须单例 Promise，勿并发打爆接口",
            tags=["pitfall", "lesson"],
            memory_type="event",
            key="pitfall:auth-refresh-singleton",
            confidence="confirmed",
        )
        left = self.hub.context("认证刷新", token_budget=1200)
        right = self.hub.context("认证刷新", token_budget=1200)
        self.assertEqual(left, right)
        self.assertIn("auth-refresh", left)

    def test_locate_finds_feature_map_paths(self) -> None:
        self.hub.upsert_map(
            agent="cursor",
            feature="billing",
            role="计费入口",
            paths=["src/billing/index.ts", "docs/billing.md"],
            commands=["npm test -- billing"],
        )
        hits = self.hub.locate("billing")
        self.assertTrue(hits)
        top = hits[0]
        self.assertEqual(top["feature"], "billing")
        self.assertIn("src/billing/index.ts", top["paths"])
        self.assertTrue((self.root / "meta" / "search-index.json").exists())


if __name__ == "__main__":
    unittest.main()
