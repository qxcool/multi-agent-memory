"""零依赖 MCP stdio 服务：暴露 orient / locate / context / map_upsert。"""

from __future__ import annotations

import json
import sys
from typing import Any

from .hub import MemoryHub, MemoryHubError, resolve_hub


SERVER_NAME = "multi-agent-memory"
SERVER_VERSION = "0.7.0"

TOOLS = [
    {
        "name": "memory_orient",
        "description": "开场：doctor/status/context 一站式装配（缓存友好）。返回 context 文本供注入。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "agent": {"type": "string"},
                "query": {"type": "string", "description": "固定检索词，利于前缀缓存"},
                "objective": {"type": "string"},
                "hub": {"type": "string", "description": "可选；省略则向上查找 .ai-memory-hub"},
                "auto_migrate": {"type": "boolean", "default": False},
            },
            "required": ["task", "agent", "query"],
        },
    },
    {
        "name": "memory_locate",
        "description": "按功能名/路径定位 feature 地图，返回 paths/commands/missing_paths。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
                "hub": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_context",
        "description": "装配分层上下文（L0→L0.5→L2，可选末尾 L1）。勿与 locate 叠成双前缀。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "task": {"type": "string"},
                "agent": {"type": "string"},
                "token_budget": {"type": "integer", "default": 2048},
                "hub": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_map_upsert",
        "description": "写入/更新功能地图（稳定 key=feature:<name>）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string"},
                "feature": {"type": "string"},
                "role": {"type": "string"},
                "paths": {"type": "array", "items": {"type": "string"}},
                "commands": {"type": "array", "items": {"type": "string"}},
                "note": {"type": "string"},
                "hub": {"type": "string"},
            },
            "required": ["agent", "feature"],
        },
    },
    {
        "name": "memory_doctor",
        "description": "检查记忆库健康状态与迁移提示。",
        "inputSchema": {
            "type": "object",
            "properties": {"hub": {"type": "string"}},
        },
    },
]


def _hub(arguments: dict[str, Any]) -> MemoryHub:
    hub_arg = arguments.get("hub")
    root = resolve_hub(hub_arg if isinstance(hub_arg, str) and hub_arg.strip() else None)
    return MemoryHub(root)


def _tool_result(payload: Any) -> dict[str, Any]:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=2)
    return {"content": [{"type": "text", "text": text}]}


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    hub = _hub(arguments)
    if name == "memory_orient":
        result = hub.orient(
            task=str(arguments["task"]),
            agent=str(arguments["agent"]),
            query=str(arguments["query"]),
            objective=str(arguments["objective"]) if arguments.get("objective") else None,
            auto_migrate=bool(arguments.get("auto_migrate") or False),
        )
        return _tool_result(result)
    if name == "memory_locate":
        result = hub.locate(str(arguments["query"]), limit=int(arguments.get("limit") or 5))
        return _tool_result(result)
    if name == "memory_context":
        text = hub.context(
            str(arguments["query"]),
            token_budget=int(arguments.get("token_budget") or 2048),
            session_task=str(arguments["task"]) if arguments.get("task") else None,
            session_agent=str(arguments["agent"]) if arguments.get("agent") else None,
        )
        return _tool_result(text)
    if name == "memory_map_upsert":
        paths = arguments.get("paths") or []
        commands = arguments.get("commands") or []
        if not isinstance(paths, list):
            paths = [str(paths)]
        if not isinstance(commands, list):
            commands = [str(commands)]
        result = hub.upsert_map(
            agent=str(arguments["agent"]),
            feature=str(arguments["feature"]),
            role=str(arguments.get("role") or ""),
            paths=[str(item) for item in paths],
            commands=[str(item) for item in commands],
            note=str(arguments.get("note") or ""),
        )
        return _tool_result(result)
    if name == "memory_doctor":
        return _tool_result(hub.doctor())
    raise MemoryHubError(f"未知工具：{name}")


def _read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        decoded = line.decode("utf-8", errors="replace").strip()
        if ":" in decoded:
            key, value = decoded.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    body = sys.stdin.buffer.read(length)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _write_message(payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii") + raw)
    sys.stdout.buffer.flush()


def _handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params") if isinstance(message.get("params"), dict) else {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        try:
            result = _call_tool(name, arguments)
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except MemoryHubError as error:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": str(error)}],
                },
            }
        except Exception as error:  # noqa: BLE001 — MCP 边界需吞异常并回报
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": f"{type(error).__name__}: {error}"}],
                },
            }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if msg_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    return None


def main() -> None:
    # Windows 控制台下尽量保持 UTF-8
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure and stream is not sys.stdin:
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except Exception:
                pass
    while True:
        message = _read_message()
        if message is None:
            break
        response = _handle(message)
        if response is not None:
            _write_message(response)


if __name__ == "__main__":
    main()
