from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "src"))

from multi_agent_memory.hub import MemoryHub


class ExistingHubCompatibilityTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("MEMORY_HUB_LEGACY_PATH"), "未提供旧记忆库路径")
    def test_existing_hub_is_readable_without_mutation(self) -> None:
        root = Path(os.environ["MEMORY_HUB_LEGACY_PATH"])
        hub = MemoryHub(root)
        report = hub.doctor()
        self.assertGreater(report["markdown_files"], 0)
        self.assertTrue(hub.recall("素材", limit=3))
        self.assertIn("Core", hub.context(max_chars=2000))


if __name__ == "__main__":
    unittest.main()
