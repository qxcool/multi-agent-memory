"""MCP stdio 协议冒烟。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SRC = PLUGIN_ROOT / "src"
sys.path.insert(0, str(SRC))

from multi_agent_memory.hub import MemoryHub


def _frame(payload: dict) -> bytes:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii") + raw


def _read_frames(buf: bytes, count: int) -> list[dict]:
    out: list[dict] = []
    offset = 0
    for _ in range(count):
        header_end = buf.find(b"\r\n\r\n", offset)
        if header_end < 0:
            break
        header = buf[offset:header_end].decode("ascii", errors="replace")
        length = 0
        for line in header.split("\r\n"):
            if line.lower().startswith("content-length:"):
                length = int(line.split(":", 1)[1].strip())
        start = header_end + 4
        end = start + length
        out.append(json.loads(buf[start:end].decode("utf-8")))
        offset = end
    return out


class McpServerTests(unittest.TestCase):
    def test_initialize_and_locate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hub_root = Path(tmp) / ".ai-memory-hub"
            hub = MemoryHub(hub_root)
            hub.init()
            hub.upsert_map(agent="cursor", feature="demo", role="演示", paths=["README.md"])

            env = os.environ.copy()
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.path.insert(0, sys.argv[1]); from multi_agent_memory.mcp_server import main; main()",
                    str(SRC),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=tmp,
                env=env,
            )
            assert proc.stdin and proc.stdout
            reqs = b"".join(
                [
                    _frame(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {},
                                "clientInfo": {"name": "test", "version": "0"},
                            },
                        }
                    ),
                    _frame({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                    _frame(
                        {
                            "jsonrpc": "2.0",
                            "id": 2,
                            "method": "tools/call",
                            "params": {
                                "name": "memory_locate",
                                "arguments": {"query": "demo", "hub": str(hub_root)},
                            },
                        }
                    ),
                ]
            )
            stdout, stderr = proc.communicate(reqs, timeout=20)
            self.assertEqual(proc.returncode, 0, stderr.decode("utf-8", errors="replace"))
            frames = _read_frames(stdout, 2)
            self.assertEqual(len(frames), 2)
            self.assertIn("serverInfo", frames[0]["result"])
            text = frames[1]["result"]["content"][0]["text"]
            self.assertIn("demo", text)


if __name__ == "__main__":
    unittest.main()
