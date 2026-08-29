from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .hub import (
    CONFIDENCE_LEVELS,
    LIST_COLLECTIONS,
    MEMORY_TYPES,
    PROMOTE_TARGETS,
    RELATION_TYPES,
    MemoryHub,
    MemoryHubError,
    resolve_hub,
    search_results_as_dict,
)


def _configure_stdio() -> None:
    """确保机器可读输出不受 Windows 本地代码页影响。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="backslashreplace")


def _parse_link(value: str) -> tuple[str, str]:
    relation, separator, target = value.partition(":")
    if not separator or not relation.strip() or not target.strip():
        raise argparse.ArgumentTypeError("关系必须使用 relation:target 格式")
    if relation.strip().casefold() not in RELATION_TYPES:
        choices = "、".join(sorted(RELATION_TYPES))
        raise argparse.ArgumentTypeError(f"关系类型必须是：{choices}")
    return relation.strip(), target.strip()


def _add_recall_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--type", dest="memory_type", choices=sorted(MEMORY_TYPES | {"legacy"}))
    parser.add_argument("--tag")
    parser.add_argument("--confidence", choices=sorted(CONFIDENCE_LEVELS))
    parser.add_argument("--collection")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memory-hub", description="宿主无关的多代理本地 Markdown 记忆库")
    parser.add_argument(
        "--hub",
        default=None,
        help="记忆库目录；省略或为 .ai-memory-hub 时从当前目录向上查找",
    )
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="初始化记忆库")
    init.add_argument("--track", action="store_true", help="允许 Git 跟踪记忆内容")

    status = subparsers.add_parser("status", help="读取或更新代理任务状态")
    status.add_argument("--task", required=True)
    status.add_argument("--agent", required=True)
    status.add_argument("--objective")
    status.add_argument("--state")
    status.add_argument("--completed", action="append", default=[])
    status.add_argument(
        "--append-completed",
        action="store_true",
        help="将 --completed 追加到已有完成项（去重），而不是整表替换",
    )
    status.add_argument("--next", dest="next_step")
    status.add_argument("--blocker")
    status.add_argument("--steps")

    remember = subparsers.add_parser("remember", help="把一条候选记忆写入 inbox")
    remember.add_argument("--agent", required=True)
    remember.add_argument("--text", required=True)
    remember.add_argument("--tags", default="")
    remember.add_argument("--type", dest="memory_type", choices=sorted(MEMORY_TYPES), default="note")
    remember.add_argument("--source-task")
    remember.add_argument("--confidence", choices=sorted(CONFIDENCE_LEVELS), default="unspecified")
    remember.add_argument("--link", action="append", type=_parse_link, default=[])

    promote = subparsers.add_parser("promote", help="把 inbox 候选记忆晋升到长期集合")
    promote.add_argument("--to", required=True, choices=sorted(PROMOTE_TARGETS))
    promote.add_argument("--id", dest="memory_id")
    promote.add_argument("--path")

    forget = subparsers.add_parser("forget", help="将记忆移入 archive/forgotten（可逆）")
    forget.add_argument("--id", dest="memory_id")
    forget.add_argument("--path")

    recall = subparsers.add_parser("recall", help="全文检索记忆")
    recall.add_argument("--query", required=True)
    recall.add_argument("--limit", type=int, default=10)
    recall.add_argument("--min-score", type=int, default=1)
    recall.add_argument("--no-archive", action="store_true")
    recall.add_argument("--include-forgotten", action="store_true")
    _add_recall_filters(recall)

    context = subparsers.add_parser("context", help="分层装配上下文（省 token）")
    context.add_argument("--query")
    context.add_argument("--max-chars", type=int, default=12000)
    context.add_argument("--token-budget", type=int)
    context.add_argument("--min-score", type=int, default=1)
    context.add_argument("--full", action="store_true", help="召回区块使用完整正文而非摘要")
    context.add_argument(
        "--core-budget",
        type=int,
        default=2000,
        help="L0 核心记忆（CORE+LESSONS）字符上限，默认 2000",
    )
    context.add_argument("--include-user", action="store_true", help="将 USER.md 纳入 L0")
    context.add_argument("--include-agents", action="store_true", help="将 AGENTS.md 纳入 L0")
    _add_recall_filters(context)

    distill = subparsers.add_parser("distill", help="任务收尾：沉淀回顾与教训")
    distill.add_argument("--task", required=True)
    distill.add_argument("--agent", required=True)
    distill.add_argument("--lesson", help="一行短教训，写入 LESSONS.md")
    distill.add_argument(
        "--pin-core",
        action="store_true",
        help="同时在 CORE.md 追加一行指针（保持 CORE 精简）",
    )
    distill.add_argument(
        "--no-promote-inbox",
        action="store_true",
        help="不自动把本任务 source_task 的 inbox 晋升到 experiences",
    )

    listing = subparsers.add_parser("list", help="列出集合内容供发现与交接")
    listing.add_argument("collection", choices=sorted(LIST_COLLECTIONS))
    listing.add_argument("--type", dest="memory_type", choices=sorted(MEMORY_TYPES | {"legacy"}))
    listing.add_argument("--tag")
    listing.add_argument("--limit", type=int, default=100)

    subparsers.add_parser("overview", help="总览活动任务、inbox 与集合规模")

    archive = subparsers.add_parser("archive", help="归档一个活动任务")
    archive.add_argument("--task", required=True)

    subparsers.add_parser("reindex", help="重建全部索引")
    subparsers.add_parser("stats", help="查看记录、类型、关系和元数据覆盖率")
    subparsers.add_parser("doctor", help="只读检查结构、编码和写锁")
    return parser


def _status_is_read_only(args: argparse.Namespace) -> bool:
    return not any(
        [
            args.objective is not None,
            args.state is not None,
            bool(args.completed),
            args.append_completed,
            args.next_step is not None,
            args.blocker is not None,
            args.steps is not None,
        ]
    )


def _print_human(command: str, result: Any) -> None:
    if command == "recall":
        if not result:
            print("未找到匹配记忆")
            return
        for item in result:
            provenance = " / ".join(
                value for value in (item.source_task, item.source_agent, item.created_at) if value
            ) or "旧版文件"
            print(
                f"[{item.score}] {item.path}\n"
                f"类型：{item.memory_type or 'legacy'}\n"
                f"原因：{item.reason}\n"
                f"来源：{provenance}\n"
                f"{item.snippet}\n"
            )
        return
    if command == "context":
        print(result)
        return
    if command == "list":
        if not result:
            print("（空）")
            return
        for item in result:
            if "task" in item:
                print(
                    f"{item['task']}/{item['agent']}: {item.get('state', '')} — {item.get('objective', '')}"
                )
            else:
                tags = ",".join(item.get("tags") or [])
                print(
                    f"{item.get('path')}: [{item.get('type')}] {item.get('title')}"
                    + (f" #{tags}" if tags else "")
                )
        return
    if command == "overview" and isinstance(result, dict):
        print(f"hub: {result.get('hub')}")
        print(f"counts: {result.get('counts')}")
        print("active_tasks:")
        for item in result.get("active_tasks") or []:
            print(f"  - {item['task']}/{item['agent']}: {item.get('state')} — {item.get('objective')}")
        print("recent_inbox:")
        for item in result.get("recent_inbox") or []:
            print(f"  - {item.get('path')}: {item.get('title')}")
        print(result.get("hint", ""))
        return
    if isinstance(result, dict):
        for key, value in result.items():
            if isinstance(value, list):
                value = "；".join(str(item) for item in value) or "无"
            print(f"{key}: {value}")
        return
    print(result)


def run(argv: Sequence[str] | None = None) -> int:
    _configure_stdio()
    parser = _parser()
    args = parser.parse_args(argv)
    hub = MemoryHub(resolve_hub(args.hub))
    try:
        if args.command == "init":
            result = hub.init(track=args.track)
        elif args.command == "status":
            if _status_is_read_only(args):
                result = hub.get_status(task=args.task, agent=args.agent)
            else:
                result = hub.update_status(
                    task=args.task,
                    agent=args.agent,
                    objective=args.objective,
                    state=args.state,
                    completed=args.completed,
                    next_step=args.next_step,
                    blocker=args.blocker,
                    steps=args.steps,
                    append_completed=args.append_completed,
                )
        elif args.command == "remember":
            tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
            result = hub.remember(
                agent=args.agent,
                text=args.text,
                tags=tags,
                memory_type=args.memory_type,
                source_task=args.source_task,
                confidence=args.confidence,
                links=args.link,
            )
        elif args.command == "promote":
            result = hub.promote(to=args.to, memory_id=args.memory_id, path=args.path)
        elif args.command == "forget":
            result = hub.forget(memory_id=args.memory_id, path=args.path)
        elif args.command == "recall":
            search_results = hub.recall(
                args.query,
                limit=args.limit,
                include_archive=not args.no_archive,
                include_forgotten=args.include_forgotten,
                min_score=args.min_score,
                memory_type=args.memory_type,
                tag=args.tag,
                confidence=args.confidence,
                collection=args.collection,
            )
            result = search_results_as_dict(search_results) if args.json else search_results
        elif args.command == "context":
            result = hub.context(
                args.query,
                max_chars=args.max_chars,
                token_budget=args.token_budget,
                min_score=args.min_score,
                full=args.full,
                memory_type=args.memory_type,
                tag=args.tag,
                confidence=args.confidence,
                collection=args.collection,
                core_budget=args.core_budget,
                include_user=args.include_user,
                include_agents=args.include_agents,
            )
        elif args.command == "distill":
            result = hub.distill(
                task=args.task,
                agent=args.agent,
                lesson=args.lesson,
                promote_inbox=not args.no_promote_inbox,
                pin_core=args.pin_core,
            )
        elif args.command == "list":
            result = hub.list_entries(
                args.collection,
                memory_type=args.memory_type,
                tag=args.tag,
                limit=args.limit,
            )
        elif args.command == "overview":
            result = hub.overview()
        elif args.command == "archive":
            result = hub.archive(args.task)
        elif args.command == "reindex":
            result = hub.reindex()
        elif args.command == "stats":
            result = hub.stats()
        else:
            result = hub.doctor()
    except MemoryHubError as error:
        if args.json:
            print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        else:
            print(f"错误：{error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=lambda value: value.__dict__))
    else:
        _print_human(args.command, result)
    if args.command == "doctor" and not result["ok"]:
        return 1
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
