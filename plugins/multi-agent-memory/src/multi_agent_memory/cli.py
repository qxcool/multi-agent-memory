from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .hub import (
    CONFIDENCE_LEVELS,
    FEEDBACK_SIGNALS,
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
    status.add_argument(
        "--query",
        help="固定本任务 context/locate 检索词（写入 status，利于前缀缓存）",
    )

    remember = subparsers.add_parser("remember", help="把一条候选记忆写入 inbox")
    remember.add_argument("--agent", required=True)
    remember.add_argument("--text", required=True)
    remember.add_argument("--tags", default="")
    remember.add_argument("--type", dest="memory_type", choices=sorted(MEMORY_TYPES), default="note")
    remember.add_argument("--source-task")
    remember.add_argument(
        "--key",
        help="稳定记忆键；相同 key 原地更新，相同正文幂等跳过",
    )
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
    context.add_argument(
        "--no-maps",
        action="store_true",
        help="不装配 L0.5 功能地图（默认会按 query locate 并稳定排序）",
    )
    context.add_argument(
        "--map-budget",
        type=int,
        default=1200,
        help="L0.5 功能地图字符上限，默认 1200",
    )
    context.add_argument("--map-limit", type=int, default=5, help="L0.5 最多条数，默认 5")
    context.add_argument(
        "--include-inferred",
        action="store_true",
        help="L2 包含 auto-summary/retrospective（默认排除，减少噪声与前缀抖动）",
    )
    context.add_argument("--task", help="可选：在末尾附加该任务 status（L1，不挤占前缀）")
    context.add_argument("--agent", help="与 --task 联用，指定代理 status")
    _add_recall_filters(context)

    orient = subparsers.add_parser("orient", help="开场一站式：status+固定检索词+缓存友好 context")
    orient.add_argument("--task", required=True)
    orient.add_argument("--agent", required=True)
    orient.add_argument("--query", required=True, help="固定检索词（同任务必须复用）")
    orient.add_argument("--objective")
    orient.add_argument("--state", default="in-progress")
    orient.add_argument("--token-budget", type=int, default=2048)
    orient.add_argument("--core-budget", type=int, default=2000)
    orient.add_argument("--map-budget", type=int, default=1200)
    orient.add_argument("--include-user", action="store_true")
    orient.add_argument("--include-agents", action="store_true")
    orient.add_argument("--no-maps", action="store_true")
    orient.add_argument("--include-inferred", action="store_true")
    orient.add_argument("--auto-migrate", action="store_true", help="若 doctor 提示落后则自动 migrate")

    close = subparsers.add_parser("close", help="收尾一站式：completed + distill + 可选 archive")
    close.add_argument("--task", required=True)
    close.add_argument("--agent", required=True)
    close.add_argument("--lesson")
    close.add_argument("--pin-core", action="store_true")
    close.add_argument("--no-promote-inbox", action="store_true")
    close.add_argument("--archive", action="store_true", help="distill 后归档任务")

    evolve = subparsers.add_parser("evolve", help="自我进化扫描（默认 dry-run；--apply 写入）")
    evolve.add_argument("--apply", action="store_true", help="执行 mark_stale / confirm 等写操作")

    distill = subparsers.add_parser(
        "distill",
        help="任务收尾：软自动总结（inferred，按 key 覆盖），可选写入 LESSONS/CORE",
    )
    distill.add_argument("--task", required=True)
    distill.add_argument("--agent", required=True)
    distill.add_argument(
        "--lesson",
        help="显式一行短教训才写入 LESSONS.md（默认仅 experiences 软总结）",
    )
    distill.add_argument(
        "--pin-core",
        action="store_true",
        help="仅在同时提供 --lesson 时，于 CORE.md 追加一行指针",
    )
    distill.add_argument(
        "--no-promote-inbox",
        action="store_true",
        help="不自动把本任务 source_task 的 inbox 晋升到 experiences",
    )

    map_parser = subparsers.add_parser("map", help="维护功能/文件地图（减少每次扫仓库）")
    map_sub = map_parser.add_subparsers(dest="map_command", required=True)
    map_upsert = map_sub.add_parser("upsert", help="创建或更新 feature 地图（写入 wiki）")
    map_upsert.add_argument("--agent", required=True)
    map_upsert.add_argument("--feature", required=True, help="功能名；自动变为 key=feature:<名>")
    map_upsert.add_argument("--role", default="", help="一句话职责")
    map_upsert.add_argument(
        "--path",
        dest="paths",
        action="append",
        default=[],
        help="关联仓库相对路径，可重复传入",
    )
    map_upsert.add_argument(
        "--command",
        dest="commands",
        action="append",
        default=[],
        help="相关命令，可重复传入",
    )
    map_upsert.add_argument("--note", default="", help="补充说明")
    map_upsert.add_argument("--source-task")
    map_upsert.add_argument("--confidence", choices=sorted(CONFIDENCE_LEVELS), default="confirmed")
    map_upsert.add_argument(
        "--replace-paths",
        action="store_true",
        help="用本次 --path 完全替换旧路径（默认合并去重）",
    )
    map_sub.add_parser("list", help="列出功能地图（按 key 稳定排序）")

    locate = subparsers.add_parser("locate", help="按功能/路径线索定位地图（短结果）")
    locate.add_argument("--query", required=True)
    locate.add_argument("--limit", type=int, default=5)
    locate.add_argument("--min-score", type=int, default=1)

    feedback = subparsers.add_parser("feedback", help="对记忆投票（useful/stale/wrong）以自我进化")
    feedback.add_argument("--signal", required=True, choices=sorted(FEEDBACK_SIGNALS))
    feedback.add_argument("--id", dest="memory_id")
    feedback.add_argument("--path")

    listing = subparsers.add_parser("list", help="列出集合内容供发现与交接")
    listing.add_argument("collection", choices=sorted(LIST_COLLECTIONS))
    listing.add_argument("--type", dest="memory_type", choices=sorted(MEMORY_TYPES | {"legacy"}))
    listing.add_argument("--tag")
    listing.add_argument("--limit", type=int, default=100)

    subparsers.add_parser("overview", help="总览活动任务、inbox 与集合规模")

    migrate = subparsers.add_parser("migrate", help="将旧记忆库升级到当前格式（幂等）")
    migrate.add_argument("--dry-run", action="store_true", help="只显示将执行的变更")
    migrate.add_argument(
        "--backfill-hash",
        action="store_true",
        help="为已有前置元数据但缺少 content_hash 的记忆补哈希",
    )

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
            args.query is not None,
        ]
    )


def _print_human(command: str, result: Any) -> None:
    if command == "locate":
        if not result:
            print("未找到匹配地图/记忆")
            return
        for item in result:
            paths = "；".join(item.get("paths") or []) or "（无路径）"
            commands = "；".join(item.get("commands") or []) or "（无）"
            print(
                f"[{item.get('score')}] {item.get('feature') or item.get('key') or item.get('path')}\n"
                f"职责：{item.get('role') or '（未填写）'}\n"
                f"路径：{paths}\n"
                f"命令：{commands}\n"
                f"文件：{item.get('path')}  置信度：{item.get('confidence')}\n"
            )
            missing = item.get("missing_paths") or []
            if missing:
                print(f"失效路径：{'；'.join(str(path) for path in missing)}\n")
        return
    if command == "orient" and isinstance(result, dict):
        print(result.get("context", ""))
        return
    if command == "evolve" and isinstance(result, dict):
        print(f"apply: {result.get('apply')}  counts: {result.get('counts')}")
        for item in result.get("planned") or []:
            print(f"- {item.get('action')}: {item.get('feature')} — {item.get('reason')}")
        return
    if command == "map" and isinstance(result, list):
        if not result:
            print("（无功能地图）")
            return
        for item in result:
            paths = "；".join(item.get("paths") or []) or "（无）"
            print(
                f"{item.get('feature')}: {item.get('role') or '（未填写）'}\n"
                f"  路径：{paths}\n"
                f"  文件：{item.get('path')}  key：{item.get('key')}\n"
            )
        return
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
                    query=args.query,
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
                key=args.key,
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
                include_maps=not args.no_maps,
                map_budget=args.map_budget,
                map_limit=args.map_limit,
                include_inferred=args.include_inferred,
                session_task=args.task,
                session_agent=args.agent,
            )
        elif args.command == "orient":
            result = hub.orient(
                task=args.task,
                agent=args.agent,
                query=args.query,
                objective=args.objective,
                state=args.state,
                token_budget=args.token_budget,
                core_budget=args.core_budget,
                map_budget=args.map_budget,
                include_user=args.include_user,
                include_agents=args.include_agents,
                include_maps=not args.no_maps,
                include_inferred=args.include_inferred,
                auto_migrate=args.auto_migrate,
            )
        elif args.command == "close":
            result = hub.close(
                task=args.task,
                agent=args.agent,
                lesson=args.lesson,
                pin_core=args.pin_core,
                promote_inbox=not args.no_promote_inbox,
                do_archive=args.archive,
            )
        elif args.command == "evolve":
            result = hub.evolve(apply=args.apply)
        elif args.command == "distill":
            result = hub.distill(
                task=args.task,
                agent=args.agent,
                lesson=args.lesson,
                promote_inbox=not args.no_promote_inbox,
                pin_core=args.pin_core,
            )
        elif args.command == "map":
            if args.map_command == "upsert":
                result = hub.upsert_map(
                    agent=args.agent,
                    feature=args.feature,
                    role=args.role,
                    paths=args.paths,
                    commands=args.commands,
                    note=args.note,
                    source_task=args.source_task,
                    confidence=args.confidence,
                    merge_paths=not args.replace_paths,
                )
            elif args.map_command == "list":
                result = hub.list_maps()
            else:
                raise MemoryHubError(f"未知 map 子命令：{args.map_command}")
        elif args.command == "locate":
            result = hub.locate(args.query, limit=args.limit, min_score=args.min_score)
        elif args.command == "feedback":
            result = hub.feedback(signal=args.signal, memory_id=args.memory_id, path=args.path)
        elif args.command == "list":
            result = hub.list_entries(
                args.collection,
                memory_type=args.memory_type,
                tag=args.tag,
                limit=args.limit,
            )
        elif args.command == "overview":
            result = hub.overview()
        elif args.command == "migrate":
            result = hub.migrate(dry_run=args.dry_run, backfill_hash=args.backfill_hash)
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
