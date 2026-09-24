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
            "防全仓",
            "GitNexus",
            "map upsert",
            "Qoder",
            "Claude",
            "any OS",
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

    def test_locate_miss_draft_and_related_fras(self) -> None:
        miss = self.hub.locate_report("totally-unknown-widget-xyz")
        self.assertEqual(0, miss["count"])
        self.assertIsNotNone(miss.get("draft_upsert"))
        self.assertIn("map upsert", str(miss["draft_upsert"].get("suggested_cli")))

        self.hub.upsert_map(
            agent="claude",
            feature="auth-client",
            role="客户端",
            paths=["src/auth/client.ts"],
        )
        self.hub.upsert_map(
            agent="claude",
            feature="auth-refresh",
            role="刷新",
            paths=["src/auth/refresh.ts"],
            links=[("uses", "feature:auth-client")],
        )
        hits = self.hub.locate("auth-refresh")
        features = {str(item.get("feature")) for item in hits}
        self.assertIn("auth-refresh", features)
        self.assertIn("auth-client", features)
        related = [item for item in hits if item.get("related_from")]
        self.assertTrue(related)

    def test_handoff_packet_and_pinned_query_context(self) -> None:
        self.hub.update_status(
            task="auth",
            agent="cursor",
            objective="修刷新",
            state="in-progress",
            query="认证刷新",
        )
        self.hub.upsert_map(
            agent="cursor",
            feature="auth-refresh",
            role="刷新",
            paths=["src/auth/refresh.ts"],
        )
        packet = self.hub.handoff(task="auth", agent="cursor", to_agent="claude")
        self.assertEqual("认证刷新", packet["query"])
        self.assertEqual("claude", packet["to_agent"])
        self.assertIn("orient", str(packet.get("suggested_orient")))
        self.assertGreaterEqual(int(packet["locate"]["count"]), 1)

        resumed = self.hub.context(
            None,
            token_budget=800,
            session_task="auth",
            session_agent="cursor",
        )
        self.assertIn("auth-refresh", resumed)

    def test_doctor_and_map_health_expose_actions(self) -> None:
        report = self.hub.doctor()
        self.assertIn("fixes", report)
        health = self.hub.map_health()
        self.assertIn("suggested_actions", health)
        overview = self.hub.overview()
        self.assertIn("continue_with", overview)
        self.assertIn("map_health", overview)


if __name__ == "__main__":
    unittest.main()
