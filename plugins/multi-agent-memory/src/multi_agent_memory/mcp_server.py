"""零依赖 MCP stdio 服务：orient / handoff / locate / coverage / seed / close 等 15 工具。"""

from __future__ import annotations

import json
import sys
from typing import Any

from .hub import MemoryHub, MemoryHubError, resolve_hub


SERVER_NAME = "multi-agent-memory"
SERVER_VERSION = "0.7.4"

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
        "name": "memory_handoff",
        "description": "跨代理交接包：status + locate + 踩坑 + 地图问题；接收方用相同 query 开场。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "agent": {"type": "string", "description": "交出方"},
                "to_agent": {"type": "string", "description": "接收方；默认同 agent"},
                "limit": {"type": "integer", "default": 5},
                "hub": {"type": "string"},
            },
            "required": ["task", "agent"],
        },
    },
    {
        "name": "memory_status",
        "description": "读取或更新任务 status（交接进度 / 固定检索词 / append_completed）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "agent": {"type": "string"},
                "objective": {"type": "string"},
                "state": {"type": "string"},
                "query": {"type": "string"},
                "next_step": {"type": "string"},
                "blocker": {"type": "string"},
                "completed": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "已完成条目；配合 append_completed",
                },
                "append_completed": {"type": "boolean", "default": False},
                "read_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "true 时只读 get_status",
                },
                "hub": {"type": "string"},
            },
            "required": ["task", "agent"],
        },
    },
    {
        "name": "memory_overview",
        "description": "总览：计数、活动任务、地图问题、map_coverage_pct/未映射热点、continue_with 续跑提示。",
        "inputSchema": {
            "type": "object",
            "properties": {"hub": {"type": "string"}},
        },
    },
    {
        "name": "memory_locate",
        "description": (
            "按功能名/路径定位 feature 地图（含 FRAS 关联扩展）。"
            "命中返回 scope.paths/commands，优先打开、勿全仓 rg；未命中返回 draft_upsert。"
        ),
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
        "description": (
            "装配分层上下文（L0→L0.5→L2，可选末尾 L1）。"
            "可省略 query：若提供 task+agent 则复用 status 固定检索词。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "task": {"type": "string"},
                "agent": {"type": "string"},
                "token_budget": {"type": "integer", "default": 2048},
                "hub": {"type": "string"},
            },
        },
    },
    {
        "name": "memory_map_upsert",
        "description": "写入/更新功能地图（稳定 key=feature:<name>；可带 authority/links/路径指纹）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string"},
                "feature": {"type": "string"},
                "role": {"type": "string"},
                "authority": {
                    "type": "string",
                    "description": "公开契约/权威约束（FRAS A）",
                },
                "paths": {"type": "array", "items": {"type": "string"}},
                "commands": {"type": "array", "items": {"type": "string"}},
                "note": {"type": "string"},
                "links": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "关系列表，每项 relation:target，如 uses:feature:auth",
                },
                "hub": {"type": "string"},
            },
            "required": ["agent", "feature"],
        },
    },
    {
        "name": "memory_map_health",
        "description": "只读检查功能地图；返回 issues 与 suggested_actions（可执行 CLI）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 200},
                "hub": {"type": "string"},
            },
        },
    },
    {
        "name": "memory_map_coverage",
        "description": "对照仓库顶层与功能地图覆盖率，列出未映射热点（新会话知项目内容）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_unmapped": {"type": "integer", "default": 40},
                "hub": {"type": "string"},
            },
        },
    },
    {
        "name": "memory_map_seed",
        "description": "按未覆盖顶层目录播种地图草稿；默认 dry_run，apply=true 才写入。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string"},
                "apply": {"type": "boolean", "default": False},
                "max_features": {"type": "integer", "default": 40},
                "hub": {"type": "string"},
            },
            "required": ["agent"],
        },
    },
    {
        "name": "memory_close",
        "description": "收尾：completed + distill；默认附带 map_health。可选 archive / evolve_maps。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "agent": {"type": "string"},
                "lesson": {"type": "string"},
                "archive": {"type": "boolean", "default": False},
                "evolve_maps": {"type": "boolean", "default": False},
                "check_maps": {"type": "boolean", "default": True},
                "hub": {"type": "string"},
            },
            "required": ["task", "agent"],
        },
    },
    {
        "name": "memory_remember",
        "description": "写入 inbox 候选记忆（踩坑/决策等）；建议带稳定 key。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string"},
                "text": {"type": "string"},
                "tags": {"type": "string", "description": "逗号分隔标签"},
                "type": {"type": "string", "default": "note"},
                "key": {"type": "string"},
                "confidence": {"type": "string", "default": "unspecified"},
                "source_task": {"type": "string"},
                "hub": {"type": "string"},
            },
            "required": ["agent", "text"],
        },
    },
    {
        "name": "memory_feedback",
        "description": "对记忆投票 useful/stale/wrong；stale 可带 reason。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "signal": {"type": "string", "enum": ["useful", "stale", "wrong"]},
                "id": {"type": "string", "description": "记忆 id（mem-…）"},
                "path": {"type": "string"},
                "reason": {"type": "string"},
                "hub": {"type": "string"},
            },
            "required": ["signal"],
        },
    },
    {
        "name": "memory_evolve",
        "description": "自我进化扫描。默认 dry-run；apply 写入 stale/confirm；apply_forget 可真正 forget。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "apply": {"type": "boolean", "default": False},
                "apply_forget": {"type": "boolean", "default": False},
                "hub": {"type": "string"},
            },
        },
    },
    {
        "name": "memory_doctor",
        "description": "检查记忆库健康；返回 warnings 与可执行 fixes。",
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
    if name == "memory_handoff":
        return _tool_result(
            hub.handoff(
                task=str(arguments["task"]),
                agent=str(arguments["agent"]),
                to_agent=str(arguments["to_agent"]) if arguments.get("to_agent") else None,
                limit=int(arguments.get("limit") or 5),
            )
        )
    if name == "memory_status":
        if bool(arguments.get("read_only")):
            return _tool_result(hub.get_status(task=str(arguments["task"]), agent=str(arguments["agent"])))
        completed = arguments.get("completed") or []
        if not isinstance(completed, list):
            completed = [str(completed)]
        return _tool_result(
            hub.update_status(
                task=str(arguments["task"]),
                agent=str(arguments["agent"]),
                objective=str(arguments["objective"]) if arguments.get("objective") else None,
                state=str(arguments["state"]) if arguments.get("state") else None,
                query=str(arguments["query"]) if arguments.get("query") else None,
                next_step=str(arguments["next_step"]) if arguments.get("next_step") else None,
                blocker=str(arguments["blocker"]) if arguments.get("blocker") else None,
                completed=[str(item) for item in completed],
                append_completed=bool(arguments.get("append_completed")),
            )
        )
    if name == "memory_overview":
        return _tool_result(hub.overview())
    if name == "memory_locate":
        result = hub.locate_report(str(arguments["query"]), limit=int(arguments.get("limit") or 5))
        return _tool_result(result)
    if name == "memory_context":
        query = str(arguments["query"]) if arguments.get("query") else None
        text_out = hub.context(
            query,
            token_budget=int(arguments.get("token_budget") or 2048),
            session_task=str(arguments["task"]) if arguments.get("task") else None,
            session_agent=str(arguments["agent"]) if arguments.get("agent") else None,
        )
        return _tool_result(text_out)
    if name == "memory_map_upsert":
        paths = arguments.get("paths") or []
        commands = arguments.get("commands") or []
        raw_links = arguments.get("links") or []
        if not isinstance(paths, list):
            paths = [str(paths)]
        if not isinstance(commands, list):
            commands = [str(commands)]
        if not isinstance(raw_links, list):
            raw_links = [str(raw_links)]
        links: list[tuple[str, str]] = []
        for item in raw_links:
            entry = str(item).strip()
            if not entry:
                continue
            relation, separator, target = entry.partition(":")
            if not separator or not relation.strip() or not target.strip():
                raise MemoryHubError("links 项必须是 relation:target 格式")
            links.append((relation.strip(), target.strip()))
        result = hub.upsert_map(
            agent=str(arguments["agent"]),
            feature=str(arguments["feature"]),
            role=str(arguments.get("role") or ""),
            authority=str(arguments.get("authority") or ""),
            paths=[str(item) for item in paths],
            commands=[str(item) for item in commands],
            note=str(arguments.get("note") or ""),
            links=links,
        )
        return _tool_result(result)
    if name == "memory_map_health":
        return _tool_result(hub.map_health(limit=int(arguments.get("limit") or 200)))
    if name == "memory_map_coverage":
        return _tool_result(hub.map_coverage(max_unmapped=int(arguments.get("max_unmapped") or 40)))
    if name == "memory_map_seed":
        return _tool_result(
            hub.map_seed(
                agent=str(arguments["agent"]),
                dry_run=not bool(arguments.get("apply")),
                max_features=int(arguments.get("max_features") or 40),
            )
        )
    if name == "memory_close":
        check_maps = arguments.get("check_maps")
        if check_maps is None:
            check_maps = True
        result = hub.close(
            task=str(arguments["task"]),
            agent=str(arguments["agent"]),
            lesson=str(arguments["lesson"]) if arguments.get("lesson") else None,
            do_archive=bool(arguments.get("archive")),
            check_maps=bool(check_maps),
            evolve_maps=bool(arguments.get("evolve_maps")),
        )
        return _tool_result(result)
    if name == "memory_remember":
        tags_raw = str(arguments.get("tags") or "")
        tags = [part.strip() for part in tags_raw.replace("，", ",").split(",") if part.strip()]
        result = hub.remember(
            agent=str(arguments["agent"]),
            text=str(arguments["text"]),
            tags=tags,
            memory_type=str(arguments.get("type") or "note"),
            key=str(arguments["key"]) if arguments.get("key") else None,
            confidence=str(arguments.get("confidence") or "unspecified"),
            source_task=str(arguments["source_task"]) if arguments.get("source_task") else None,
        )
        return _tool_result(result)
    if name == "memory_feedback":
        if not arguments.get("id") and not arguments.get("path"):
            raise MemoryHubError("feedback 需要 id 或 path")
        result = hub.feedback(
            signal=str(arguments["signal"]),
            memory_id=str(arguments["id"]) if arguments.get("id") else None,
            path=str(arguments["path"]) if arguments.get("path") else None,
            reason=str(arguments["reason"]) if arguments.get("reason") else None,
        )
        return _tool_result(result)
    if name == "memory_evolve":
        return _tool_result(
            hub.evolve(
                apply=bool(arguments.get("apply")),
                apply_forget=bool(arguments.get("apply_forget")),
            )
        )
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
