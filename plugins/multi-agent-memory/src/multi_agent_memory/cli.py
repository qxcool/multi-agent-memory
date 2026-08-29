from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .hub import MemoryHub, MemoryHubError, search_results_as_dict


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memory-hub", description="面向多代理协作的本地 Markdown 记忆库")
    parser.add_argument("--hub", default=".ai-memory-hub", help="记忆库目录，默认 .ai-memory-hub")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="初始化记忆库")
    init.add_argument("--track", action="store_true", help="允许 Git 跟踪记忆内容")

    status = subparsers.add_parser("status", help="创建或更新代理任务状态")
    status.add_argument("--task", required=True)
    status.add_argument("--agent", required=True)
    status.add_argument("--objective")
    status.add_argument("--state")
    status.add_argument("--completed", action="append", default=[])
    status.add_argument("--next", dest="next_step")
    status.add_argument("--blocker")
    status.add_argument("--steps")

    remember = subparsers.add_parser("remember", help="把一条候选记忆写入 inbox")
    remember.add_argument("--agent", required=True)
    remember.add_argument("--text", required=True)
    remember.add_argument("--tags", default="")

    recall = subparsers.add_parser("recall", help="全文检索记忆")
    recall.add_argument("--query", required=True)
    recall.add_argument("--limit", type=int, default=10)
    recall.add_argument("--no-archive", action="store_true")

    context = subparsers.add_parser("context", help="生成适合交给代理的紧凑上下文")
    context.add_argument("--query")
    context.add_argument("--max-chars", type=int, default=12000)

    archive = subparsers.add_parser("archive", help="归档一个活动任务")
    archive.add_argument("--task", required=True)

    subparsers.add_parser("reindex", help="重建全部索引")
    subparsers.add_parser("doctor", help="只读检查结构、编码和写锁")
    return parser


def _print_human(command: str, result: Any) -> None:
    if command == "recall":
        if not result:
            print("未找到匹配记忆")
            return
        for item in result:
            print(f"[{item.score}] {item.path}\n{item.snippet}\n")
        return
    if command == "context":
        print(result)
        return
    if isinstance(result, dict):
        for key, value in result.items():
            if isinstance(value, list):
                value = "；".join(str(item) for item in value) or "无"
            print(f"{key}: {value}")
        return
    print(result)


def run(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    hub = MemoryHub(Path(args.hub))
    try:
        if args.command == "init":
            result = hub.init(track=args.track)
        elif args.command == "status":
            result = hub.update_status(
                task=args.task,
                agent=args.agent,
                objective=args.objective,
                state=args.state,
                completed=args.completed,
                next_step=args.next_step,
                blocker=args.blocker,
                steps=args.steps,
            )
        elif args.command == "remember":
            tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
            result = hub.remember(agent=args.agent, text=args.text, tags=tags)
        elif args.command == "recall":
            search_results = hub.recall(args.query, limit=args.limit, include_archive=not args.no_archive)
            result = search_results_as_dict(search_results) if args.json else search_results
        elif args.command == "context":
            result = hub.context(args.query, max_chars=args.max_chars)
        elif args.command == "archive":
            result = hub.archive(args.task)
        elif args.command == "reindex":
            result = hub.reindex()
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
