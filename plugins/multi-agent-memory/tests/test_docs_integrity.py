"""文档完整性：防止 PowerShell 反引号转义污染 Markdown；多宿主覆盖。"""

from __future__ import annotations

import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PLUGIN_ROOT / "skills" / "multi-agent-memory"
ADAPTERS = PLUGIN_ROOT / "adapters"
HOSTS = ("claude", "codex", "cursor", "deepseek-harness", "opencode", "qoder")
# 文档里各短名带反引号；安装脚本末尾提示不带反引号
AGENT_SHORT_DOC = "`claude` | `codex` | `cursor` | `deepseek` | `opencode` | `qoder`"
AGENT_SHORT_PLAIN = "claude | codex | cursor | deepseek | opencode | qoder"


class DocsIntegrityTests(unittest.TestCase):
    def test_skill_markdown_has_no_c0_controls(self) -> None:
        bad: list[str] = []
        for path in SKILL_ROOT.rglob("*.md"):
            data = path.read_bytes()
            for index, byte in enumerate(data):
                if byte < 32 and byte not in (9, 10, 13):
                    bad.append(f"{path.relative_to(PLUGIN_ROOT)}@{index}=0x{byte:02x}")
                    break
        self.assertEqual([], bad)

    def test_storage_feature_map_section_intact(self) -> None:
        text = (SKILL_ROOT / "references" / "storage.md").read_text(encoding="utf-8")
        self.assertIn("`feature:<功能名>`", text)
        self.assertIn("`path_fingerprints`", text)
        self.assertIn("`evolve --apply`", text)
        self.assertIn("locate_report", text)

    def test_agent_short_names_include_qoder(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        commands = (SKILL_ROOT / "references" / "commands.md").read_text(encoding="utf-8")
        self.assertIn(AGENT_SHORT_DOC, skill)
        self.assertIn(AGENT_SHORT_DOC, commands)
        self.assertIn("Qoder", skill)

    def test_shared_workflow_and_host_adapters(self) -> None:
        shared = ADAPTERS / "shared-workflow.md"
        self.assertTrue(shared.is_file())
        shared_text = shared.read_text(encoding="utf-8")
        self.assertIn(AGENT_SHORT_DOC, shared_text)
        self.assertIn("memory-hub locate", shared_text)
        self.assertIn("cross-platform.md", shared_text)
        for host in HOSTS:
            readme = ADAPTERS / host / "README.md"
            self.assertTrue(readme.is_file(), msg=f"missing {readme}")
            text = readme.read_text(encoding="utf-8")
            self.assertIn("shared-workflow.md", text)
            self.assertIn("locate", text.lower())

    def test_cross_platform_guide(self) -> None:
        path = ADAPTERS / "cross-platform.md"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("install.ps1", text)
        self.assertIn("install.sh", text)
        self.assertIn("MEMORY_HUB_ROOT", text)
        self.assertIn("仓库相对", text)
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("cross-platform.md", skill)

    def test_install_scripts_cover_qoder(self) -> None:
        ps1 = (PLUGIN_ROOT / "scripts" / "install.ps1").read_text(encoding="utf-8")
        sh = (PLUGIN_ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        for text in (ps1, sh):
            self.assertIn("qoder", text)
            self.assertIn(AGENT_SHORT_PLAIN, text)
        self.assertIn("ProjectCursor", ps1)
        self.assertIn("project-cursor", sh)
        self.assertIn(".qoder\\skills\\multi-agent-memory", ps1)
        self.assertIn(".qoder/skills/multi-agent-memory", sh)

    def test_host_readmes_have_unix_install_and_mcp(self) -> None:
        self.assertTrue((ADAPTERS / "mcp.stdio.example.json").is_file())
        for host in HOSTS:
            text = (ADAPTERS / host / "README.md").read_text(encoding="utf-8")
            self.assertIn("install.sh", text, msg=f"{host} missing install.sh")
            if host == "opencode":
                self.assertIn(".config/opencode", text)
            examples = list((ADAPTERS / host).glob("mcp*.example*")) + list(
                (ADAPTERS / host).glob("opencode.jsonc.example")
            )
            self.assertTrue(examples, msg=f"{host} missing mcp example")


if __name__ == "__main__":
    unittest.main()
