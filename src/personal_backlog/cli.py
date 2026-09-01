from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from personal_backlog import __version__
from personal_backlog.assistant import context_for, get_provider
from personal_backlog.model import BacklogError, PRIORITIES, SIZES, STATES, Task
from personal_backlog.storage import (
    MISSING,
    add_project_agent_instructions,
    check_backlog,
    create_task,
    create_tasks,
    discover_backlog,
    get_task,
    init_backlog,
    list_tasks,
    render_template,
    serialize_task,
    upgrade_backlog,
    update_task,
)


def _nullable(value: str) -> str | None:
    return None if value.lower() in {"none", "null", "-"} else value


def _body_value(body: str | None, body_file: str | None) -> str | object:
    if body is not None and body_file is not None:
        raise BacklogError("use either --body or --body-file, not both")
    if body is not None:
        return body
    if body_file is not None:
        if body_file == "-":
            return sys.stdin.read()
        try:
            return Path(body_file).read_text(encoding="utf-8")
        except OSError as exc:
            raise BacklogError(f"could not read {body_file}: {exc}") from exc
    return MISSING


def _templated_body(args: argparse.Namespace, backlog_dir: Path) -> str | object:
    body = _body_value(args.body, args.body_file)
    has_structured_fields = any((args.context, args.outcome, args.criteria))
    if body is not MISSING and (args.template or has_structured_fields):
        raise BacklogError("use either --body/--body-file or --template and structured fields")
    if args.template or has_structured_fields:
        return render_template(
            backlog_dir,
            args.template or "standard",
            context=args.context,
            outcome=args.outcome,
            criteria=args.criteria,
        )
    return body


def _batch_value(input_file: str) -> list[dict[str, object]]:
    try:
        raw = sys.stdin.read() if input_file == "-" else Path(input_file).read_text(encoding="utf-8")
    except OSError as exc:
        raise BacklogError(f"could not read {input_file}: {exc}") from exc
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BacklogError(f"invalid batch JSON: {exc.msg}") from exc
    if isinstance(value, dict) and set(value) == {"tasks"}:
        value = value["tasks"]
    if not isinstance(value, list):
        raise BacklogError("batch JSON must be an array of task objects or {\"tasks\": [...]}")
    return value


def _add_output_options(parser: argparse.ArgumentParser) -> None:
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="emit JSON")
    output.add_argument("--toon", action="store_true", help="emit compact TOON for LLM context")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backlog",
        description="A tiny, Git-friendly Markdown backlog.",
    )
    parser.add_argument(
        "--backlog",
        type=Path,
        help="backlog directory (otherwise discovered from the current directory)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="create a backlog directory")
    init_parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="directory to create (default: ./backlog)",
    )
    init_parser.add_argument(
        "--add-agent-instructions",
        action="store_true",
        help="create or append a project-root AGENTS.md pointer",
    )

    upgrade_parser = commands.add_parser(
        "upgrade", help="preview or apply generated backlog integration updates"
    )
    upgrade_parser.add_argument("--apply", action="store_true", help="write the proposed updates")
    _add_output_options(upgrade_parser)

    add_parser = commands.add_parser("add", help="create a task")
    add_parser.add_argument("title")
    add_parser.add_argument("--release", type=_nullable, default=None)
    add_parser.add_argument("--priority", type=int, choices=PRIORITIES, default=3)
    add_parser.add_argument("--size", choices=(*SIZES, "none"), default=None)
    add_parser.add_argument("--state", choices=STATES, default="todo")
    add_parser.add_argument("--tag", dest="tags", action="append", default=[], metavar="TAG")
    add_parser.add_argument("--body")
    add_parser.add_argument("--body-file", metavar="PATH", help="read Markdown from PATH or -")
    add_parser.add_argument("--template", metavar="NAME", help="initialize the body from a template")
    add_parser.add_argument("--context", help="fill the Context section of a template")
    add_parser.add_argument("--outcome", help="fill the Desired outcome section of a template")
    add_parser.add_argument(
        "--criteria", action="append", help="add one Acceptance criteria item (repeatable)"
    )
    _add_output_options(add_parser)

    assistant_parser = commands.add_parser(
        "add-assistant", help="ask a configured AI provider to propose one task"
    )
    assistant_parser.add_argument("request", help="natural-language description of the task")
    assistant_parser.add_argument(
        "--provider", default="apple-intelligence", help="provider name (default: apple-intelligence)"
    )
    assistant_parser.add_argument(
        "--apply", action="store_true", help="create the proposal after validation"
    )
    _add_output_options(assistant_parser)

    batch_parser = commands.add_parser("add-batch", help="create tasks from a JSON batch")
    batch_parser.add_argument("--file", default="-", metavar="PATH", help="JSON file, or - for stdin")
    _add_output_options(batch_parser)

    list_parser = commands.add_parser("list", help="list tasks")
    list_parser.add_argument("--state", choices=STATES)
    list_parser.add_argument("--release", type=_nullable, default=MISSING)
    list_parser.add_argument("--tag", dest="tags", action="append", default=[], metavar="TAG")
    _add_output_options(list_parser)

    show_parser = commands.add_parser("show", help="show one task")
    show_parser.add_argument("id")
    _add_output_options(show_parser)

    update_parser = commands.add_parser("update", help="change one task")
    update_parser.add_argument("id")
    update_parser.add_argument("--title", default=MISSING)
    update_parser.add_argument("--release", type=_nullable, default=MISSING)
    update_parser.add_argument("--priority", type=int, choices=PRIORITIES, default=MISSING)
    update_parser.add_argument("--size", choices=(*SIZES, "none"), default=MISSING)
    update_parser.add_argument("--state", choices=STATES, default=MISSING)
    update_tags = update_parser.add_mutually_exclusive_group()
    update_tags.add_argument("--tag", dest="tags", action="append", default=MISSING, metavar="TAG")
    update_tags.add_argument("--clear-tags", dest="tags", action="store_const", const=[])
    update_parser.add_argument("--body")
    update_parser.add_argument("--body-file", metavar="PATH", help="read Markdown from PATH or -")
    _add_output_options(update_parser)

    check_parser = commands.add_parser("check", help="validate every backlog file")
    _add_output_options(check_parser)

    web_parser = commands.add_parser("web", help="open the local web app (board and editor)")
    web_parser.add_argument("--port", type=int, default=8765)
    web_parser.add_argument("--no-browser", action="store_true")
    web_parser.add_argument(
        "--read-only", "--readonly", "-r", dest="read_only", action="store_true", help="start in read-only mode"
    )

    serve_parser = commands.add_parser("serve", help="open the local web app (alias for web)")
    serve_parser.add_argument("--port", type=int, default=8765)
    serve_parser.add_argument("--no-browser", action="store_true")
    serve_parser.add_argument(
        "--read-only", "--readonly", "-r", dest="read_only", action="store_true", help="start in read-only mode"
    )
    return parser


def _json_dump(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _structured_dump(args: argparse.Namespace, value: object) -> bool:
    if args.json:
        _json_dump(value)
        return True
    if args.toon:
        from personal_backlog.toon import dumps

        print(dumps(_toon_value(value)))
        return True
    return False


def _toon_value(value: object) -> object:
    """Project task tags into one compact, display-only TOON scalar."""
    if isinstance(value, list):
        return [_toon_value(item) for item in value]
    if not isinstance(value, dict):
        return value

    rendered = {key: _toon_value(item) for key, item in value.items()}
    if {"id", "title", "state"}.issubset(rendered):
        tags = rendered.get("tags")
        if isinstance(tags, list) and all(isinstance(tag, str) for tag in tags):
            rendered["tags"] = " · ".join(tags) or None
        elif tags is None:
            rendered["tags"] = None
    return rendered


def _print_table(tasks: list[Task]) -> None:
    if not tasks:
        print("No tasks.")
        return
    headers = ("ID", "STATE", "PRI", "SIZE", "RELEASE", "TITLE")
    rows = [
        (
            task.id,
            task.state,
            str(task.priority),
            task.size or "-",
            task.release or "-",
            task.title,
        )
        for task in tasks
    ]
    widths = [max(len(headers[index]), *(len(row[index]) for row in rows)) for index in range(5)]
    print(
        f"{headers[0]:<{widths[0]}}  {headers[1]:<{widths[1]}}  "
        f"{headers[2]:>{widths[2]}}  {headers[3]:<{widths[3]}}  "
        f"{headers[4]:<{widths[4]}}  {headers[5]}"
    )
    for row in rows:
        print(
            f"{row[0]:<{widths[0]}}  {row[1]:<{widths[1]}}  "
            f"{row[2]:>{widths[2]}}  {row[3]:<{widths[3]}}  "
            f"{row[4]:<{widths[4]}}  {row[5]}"
        )


def run(args: argparse.Namespace) -> int:
    if args.command == "init":
        if args.backlog is not None and args.path is not None:
            raise BacklogError("use either --backlog or an init path, not both")
        destination = args.backlog or args.path or (Path.cwd() / "backlog")
        created = init_backlog(destination)
        print(f"Created backlog at {created}")
        if args.add_agent_instructions:
            agent_path, changed = add_project_agent_instructions(created)
            action = "Added backlog instructions to" if changed else "Backlog instructions already in"
            print(f"{action} {agent_path}")
        return 0

    backlog_dir = discover_backlog(explicit=args.backlog)

    if args.command == "upgrade":
        result = upgrade_backlog(backlog_dir, apply=args.apply)
        if not _structured_dump(args, result):
            source = result["from_version"] or "untracked"
            print(f"Personal Backlog {source} → {result['to_version']}")
            if result["changes"]:
                verb = "Updated" if args.apply else "Would update"
                print(f"{verb}:")
                for change in result["changes"]:
                    print(f"  {change['action']}: {change['path']}")
            else:
                print("Generated integration files are already current.")
            if not args.apply and result["changes"]:
                if sys.stdin.isatty():
                    try:
                        answer = input("Apply now? [y/N] ")
                    except EOFError:
                        answer = ""
                    if answer.strip().casefold() in {"y", "yes"}:
                        upgrade_backlog(backlog_dir, apply=True)
                        print("Applied changes.")
                    else:
                        print("No changes applied.")
                else:
                    print("Run `backlog upgrade --apply` to apply these changes.")
        return 0

    if args.command == "add":
        body = _templated_body(args, backlog_dir)
        task = create_task(
            backlog_dir,
            title=args.title,
            release=args.release,
            priority=args.priority,
            size=None if args.size == "none" else args.size,
            state=args.state,
            tags=args.tags,
            body="" if body is MISSING else str(body),
        )
        if not _structured_dump(args, task.as_dict()):
            print(f"Created {task.id}: {task.title}")
        return 0

    if args.command == "add-assistant":
        context = context_for(backlog_dir, args.request)
        provider = get_provider(args.provider)
        proposal = provider.propose(context)
        if args.apply:
            values = proposal.as_dict()
            task = create_task(backlog_dir, **values)
            output: object = {"provider": provider.name, "applied": True, "task": task.as_dict()}
            if not _structured_dump(args, output):
                print(f"Created {task.id}: {task.title} (proposed by {provider.name})")
        else:
            output = {"provider": provider.name, "applied": False, "task": proposal.as_dict()}
            if not _structured_dump(args, output):
                print(f"Proposal from {provider.name}; no task was created:")
                print(serialize_task(Task(
                    id="T0000", title=proposal.title, release=proposal.release,
                    priority=proposal.priority, size=proposal.size, state="todo",
                    created="1970-01-01T00:00:00+00:00", done=None, body=proposal.body,
                )), end="")
                print("Run the same command with --apply to create a validated task.")
        return 0

    if args.command == "add-batch":
        tasks = create_tasks(backlog_dir, _batch_value(args.file))
        values = [task.as_dict() for task in tasks]
        if not _structured_dump(args, values):
            print("Created " + ", ".join(f"{task.id}: {task.title}" for task in tasks))
        return 0

    if args.command == "list":
        tasks = list_tasks(backlog_dir)
        if args.state:
            tasks = [task for task in tasks if task.state == args.state]
        if args.release is not MISSING:
            tasks = [task for task in tasks if task.release == args.release]
        if args.tags:
            wanted_tags = {tag.casefold() for tag in args.tags}
            tasks = [
                task
                for task in tasks
                if wanted_tags.issubset({tag.casefold() for tag in task.tags})
            ]
        if not _structured_dump(args, [task.as_dict(include_body=False) for task in tasks]):
            _print_table(tasks)
        return 0

    if args.command == "show":
        task = get_task(backlog_dir, args.id)
        if not _structured_dump(args, task.as_dict()):
            print(serialize_task(task), end="")
        return 0

    if args.command == "update":
        body = _body_value(args.body, args.body_file)
        values = {
            "title": args.title,
            "release": args.release,
            "priority": args.priority,
            "size": args.size,
            "state": args.state,
            "tags": args.tags,
            "body": body,
        }
        if args.size == "none":
            values["size"] = None
        if all(value is MISSING for value in values.values()):
            raise BacklogError("nothing to update")
        task = update_task(backlog_dir, args.id, **values)
        if not _structured_dump(args, task.as_dict()):
            print(f"Updated {task.id}: {task.title}")
        return 0

    if args.command == "check":
        issues = check_backlog(backlog_dir)
        if _structured_dump(args, {"ok": not issues, "issues": issues}):
            pass
        elif issues:
            for issue in issues:
                print(f"{issue['file']}: {issue['error']}", file=sys.stderr)
        else:
            print("Backlog is valid.")
        return 1 if issues else 0

    if args.command in {"web", "serve"}:
        from personal_backlog.server import serve

        serve(backlog_dir, port=args.port, open_browser=not args.no_browser, read_only=args.read_only)
        return 0

    raise AssertionError(f"unhandled command {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except BacklogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130
