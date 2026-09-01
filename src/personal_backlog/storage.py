from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import tomllib
import unicodedata
from typing import Any

from personal_backlog import __version__
from personal_backlog.model import (
    BacklogError,
    ConflictError,
    NotFoundError,
    STATES,
    Task,
    ValidationError,
    normalize_tags,
)


SCHEMA_VERSION = 1
CONFIG_NAME = "backlog.toml"
VERSION_NAME = ".version"
TASK_KEYS = ("id", "title", "release", "priority", "size", "state", "created", "done")
OPTIONAL_TASK_KEYS = ("tags",)
MISSING = object()
MANAGED_AGENT_BLOCK = re.compile(
    r"<!-- personal-backlog:start -->.*?<!-- personal-backlog:end -->\n?", re.DOTALL
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def discover_backlog(start: Path | None = None, explicit: Path | None = None) -> Path:
    if explicit is not None:
        candidate = explicit.expanduser().resolve()
        if not (candidate / CONFIG_NAME).is_file():
            raise NotFoundError(f"no {CONFIG_NAME} found in {candidate}")
        return candidate

    current = (start or Path.cwd()).resolve()
    for parent in (current, *current.parents):
        if (parent / CONFIG_NAME).is_file() and parent.name == "backlog":
            return parent
        candidate = parent / "backlog"
        if (candidate / CONFIG_NAME).is_file():
            return candidate
    raise NotFoundError("no backlog found; run 'backlog init' from a project directory")


def validate_backlog(backlog_dir: Path) -> None:
    config_path = backlog_dir / CONFIG_NAME
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise NotFoundError(f"missing {config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValidationError(f"invalid {config_path.name}: {exc}") from exc
    if config.get("schema") != SCHEMA_VERSION:
        raise ValidationError(
            f"unsupported backlog schema {config.get('schema')!r}; expected {SCHEMA_VERSION}"
        )
    if not (backlog_dir / "tasks").is_dir():
        raise ValidationError(f"missing tasks directory in {backlog_dir}")


def init_backlog(backlog_dir: Path) -> Path:
    backlog_dir = backlog_dir.expanduser().resolve()
    config_path = backlog_dir / CONFIG_NAME
    if config_path.exists():
        raise BacklogError(f"a backlog already exists at {backlog_dir}")
    backlog_dir.mkdir(parents=True, exist_ok=True)
    (backlog_dir / "tasks").mkdir(exist_ok=True)
    _atomic_write(config_path, f"schema = {SCHEMA_VERSION}\n")
    _atomic_write(backlog_dir / "README.md", GENERATED_README)
    _atomic_write(backlog_dir / "AGENTS.md", GENERATED_AGENTS)
    _atomic_write(backlog_dir / VERSION_NAME, f"{__version__}\n")
    return backlog_dir


def project_agent_instructions(backlog_dir: Path) -> str:
    """Return the managed project-root pointer for an initialized backlog."""
    relative = backlog_dir.name
    return f"""<!-- personal-backlog:start -->
## Project backlog

This project tracks future work in `{relative}/`. Before planning work, capturing
conversation context, or changing backlog items, read `{relative}/AGENTS.md` and
use the `backlog` CLI. Inspect existing tasks before creating new ones, avoid
duplicates, and finish backlog changes with `backlog check`.
<!-- personal-backlog:end -->
"""


def add_project_agent_instructions(backlog_dir: Path) -> tuple[Path, bool]:
    """Create or refresh the managed backlog pointer without replacing other instructions."""
    backlog_dir = backlog_dir.resolve()
    agent_path = backlog_dir.parent / "AGENTS.md"
    existing = agent_path.read_text(encoding="utf-8") if agent_path.exists() else ""
    content = _project_agent_content(existing, backlog_dir)
    _atomic_write(agent_path, content)
    return agent_path, content != existing


def _project_agent_content(existing: str, backlog_dir: Path) -> str:
    block = project_agent_instructions(backlog_dir)
    if MANAGED_AGENT_BLOCK.search(existing):
        return MANAGED_AGENT_BLOCK.sub(block, existing, count=1)
    return f"{existing.rstrip()}\n\n{block}" if existing.strip() else block


def _read_version_marker(backlog_dir: Path) -> str | None:
    path = backlog_dir / VERSION_NAME
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BacklogError(f"could not read {path}: {exc}") from exc
    version = raw.rstrip("\n")
    if not version or "\n" in version or "\r" in version or version != version.strip():
        raise ValidationError(f"{VERSION_NAME} must contain one non-empty version string")
    return version


def upgrade_backlog(backlog_dir: Path, *, apply: bool = False) -> dict[str, Any]:
    """Preview or apply a generated-file upgrade for an existing backlog."""
    backlog_dir = backlog_dir.resolve()
    validate_backlog(backlog_dir)
    current_version = _read_version_marker(backlog_dir)
    agent_path = backlog_dir.parent / "AGENTS.md"
    existing_agent = agent_path.read_text(encoding="utf-8") if agent_path.exists() else ""
    targets = [
        (backlog_dir / "README.md", GENERATED_README),
        (backlog_dir / "AGENTS.md", GENERATED_AGENTS),
        (agent_path, _project_agent_content(existing_agent, backlog_dir)),
        (backlog_dir / VERSION_NAME, f"{__version__}\n"),
    ]
    changes = [
        {
            "path": str(path.relative_to(backlog_dir.parent)),
            "action": "create" if not path.exists() else "update",
        }
        for path, content in targets
        if not path.exists() or path.read_text(encoding="utf-8") != content
    ]
    if apply:
        marker_path = backlog_dir / VERSION_NAME
        for path, content in targets:
            if path != marker_path and (not path.exists() or path.read_text(encoding="utf-8") != content):
                _atomic_write(path, content)
        marker_content = f"{__version__}\n"
        if not marker_path.exists() or marker_path.read_text(encoding="utf-8") != marker_content:
            _atomic_write(marker_path, marker_content)
    return {
        "applied": apply,
        "from_version": current_version,
        "to_version": __version__,
        "changes": changes,
    }


def _parse_scalar(raw: str, *, line_number: int) -> Any:
    raw = raw.strip()
    if not raw:
        raise ValidationError(f"empty metadata value on line {line_number}; use null")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        if raw in {"null", "~"}:
            return None
        if re.fullmatch(r"-?\d+", raw):
            return int(raw)
        if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
            return raw[1:-1].replace("''", "'")
        if raw[0] in "[{\"'" or raw[-1] in "]}\"'":
            raise ValidationError(f"invalid quoted metadata value on line {line_number}")
        return raw


def parse_task(text: str, source: str = "task") -> Task:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValidationError(f"{source}: task must start with YAML front matter")
    try:
        closing = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise ValidationError(f"{source}: YAML front matter is not closed") from exc

    metadata: dict[str, Any] = {}
    for index, line in enumerate(lines[1:closing], start=2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            raise ValidationError(f"{source}: invalid metadata on line {index}")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if key not in (*TASK_KEYS, *OPTIONAL_TASK_KEYS):
            raise ValidationError(f"{source}: unknown metadata field {key!r}")
        if key in metadata:
            raise ValidationError(f"{source}: duplicate metadata field {key!r}")
        metadata[key] = _parse_scalar(raw_value, line_number=index)

    missing = [key for key in TASK_KEYS if key not in metadata]
    if missing:
        raise ValidationError(f"{source}: missing metadata: {', '.join(missing)}")
    metadata.setdefault("tags", [])
    body = "\n".join(lines[closing + 1 :]).strip("\n")
    try:
        task = Task(**metadata, body=body)
    except TypeError as exc:
        raise ValidationError(f"{source}: invalid metadata types") from exc
    try:
        task.validate()
    except ValidationError as exc:
        raise ValidationError(f"{source}: {exc}") from exc
    return task


def _format_scalar(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def serialize_task(task: Task) -> str:
    task.validate()
    metadata = task.as_dict(include_body=False)
    lines = ["---"]
    lines.extend(f"{key}: {_format_scalar(metadata[key])}" for key in TASK_KEYS)
    if task.tags:
        lines.append(f"tags: {_format_scalar(task.tags)}")
    lines.extend(("---", ""))
    if task.body:
        lines.extend((task.body.rstrip(), ""))
    return "\n".join(lines)


def slugify(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug[:60].rstrip("-") or "task"


def normalize_id(task_id: str) -> str:
    value = task_id.strip().upper()
    if value.isdigit():
        value = f"T{int(value):04d}"
    elif re.fullmatch(r"T\d+", value):
        value = f"T{int(value[1:]):04d}"
    return value


def _task_files(backlog_dir: Path) -> list[Path]:
    validate_backlog(backlog_dir)
    return sorted((backlog_dir / "tasks").glob("*.md"))


def list_tasks(backlog_dir: Path) -> list[Task]:
    tasks = [parse_task(path.read_text(encoding="utf-8"), path.name) for path in _task_files(backlog_dir)]
    state_order = {state: index for index, state in enumerate(STATES)}
    return sorted(tasks, key=lambda task: (state_order[task.state], task.priority, task.id))


def release_sort_key(release: str) -> tuple[tuple[int, int | str], ...]:
    """Sort release labels naturally, with the rolling `next` release last."""
    if release.casefold() == "next":
        return ((2, "next"),)
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.findall(r"\d+|\D+", release)
    )


def current_release(backlog_dir: Path) -> str | None:
    """Best-effort earliest release that still contains unfinished work.

    Tasks without a release are intentionally excluded: they do not describe a
    release to select.  Callers can treat ``None`` as "leave the current view
    unchanged", including when a malformed or inaccessible backlog prevents a
    decision.
    """
    try:
        grouped: dict[str, list[Task]] = {}
        for task in list_tasks(backlog_dir):
            if task.release is not None:
                grouped.setdefault(task.release, []).append(task)
        for release in sorted(grouped, key=release_sort_key):
            if any(task.state != "done" for task in grouped[release]):
                return release
    except (BacklogError, OSError, TypeError, ValueError):
        pass
    return None


def _find_task_path(backlog_dir: Path, task_id: str) -> Path:
    wanted = normalize_id(task_id)
    matches: list[Path] = []
    for path in _task_files(backlog_dir):
        if path.name == f"{wanted}.md" or path.name.startswith(f"{wanted}-"):
            matches.append(path)
    if not matches:
        raise NotFoundError(f"task {wanted} not found")
    if len(matches) > 1:
        raise ValidationError(f"multiple files found for task {wanted}")
    return matches[0]


def get_task(backlog_dir: Path, task_id: str) -> Task:
    path = _find_task_path(backlog_dir, task_id)
    task = parse_task(path.read_text(encoding="utf-8"), path.name)
    if task.id != normalize_id(task_id):
        raise ValidationError(f"{path.name}: id does not match its filename")
    return task


def task_revision(backlog_dir: Path, task_id: str) -> str:
    content = _find_task_path(backlog_dir, task_id).read_bytes()
    return hashlib.sha256(content).hexdigest()


def _next_id(backlog_dir: Path) -> str:
    numbers = [int(task.id[1:]) for task in list_tasks(backlog_dir)]
    return f"T{max(numbers, default=0) + 1:04d}"


def create_task(
    backlog_dir: Path,
    *,
    title: str,
    release: str | None = None,
    priority: int = 3,
    size: str | None = None,
    state: str = "todo",
    tags: list[str] | None = None,
    body: str = "",
) -> Task:
    validate_backlog(backlog_dir)
    if not isinstance(title, str):
        raise ValidationError("title must be text")
    if release is not None and not isinstance(release, str):
        raise ValidationError("release must be text or null")
    if not isinstance(body, str):
        raise ValidationError("Markdown body must be text")
    for _ in range(100):
        task_id = _next_id(backlog_dir)
        timestamp = now_iso()
        task = Task(
            id=task_id,
            title=title.strip(),
            release=release.strip() if release is not None else None,
            priority=priority,
            size=size,
            state=state,
            created=timestamp,
            done=timestamp if state == "done" else None,
            tags=normalize_tags(tags),
            body=body.strip("\n"),
        )
        task.validate()
        path = backlog_dir / "tasks" / f"{task.id}-{slugify(task.title)}.md"
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialize_task(task))
        return task
    raise ConflictError("could not allocate a task id")


BUILTIN_TEMPLATES = {
    "standard": """## Context


## Desired outcome


## Decisions and constraints


## Acceptance criteria
""",
    "feature": """## Context


## Desired outcome


## Decisions and constraints


## Acceptance criteria
""",
    "bug": """## Context


## Current behavior


## Expected behavior


## Acceptance criteria
""",
    "agent": """## Context


## Desired outcome


## Decisions and constraints


## Current state


## Notes
""",
}


def templates(backlog_dir: Path) -> dict[str, str]:
    """Return the built-in templates extended by `[templates]` in backlog.toml."""
    validate_backlog(backlog_dir)
    try:
        config = tomllib.loads((backlog_dir / CONFIG_NAME).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:  # validate_backlog gives normal user errors.
        raise ValidationError(f"invalid {CONFIG_NAME}: {exc}") from exc
    configured = config.get("templates", {})
    if not isinstance(configured, dict) or not all(
        isinstance(name, str) and isinstance(body, str) and body.strip()
        for name, body in configured.items()
    ):
        raise ValidationError("templates must be a table of non-empty Markdown strings")
    return {**BUILTIN_TEMPLATES, **configured}


def render_template(
    backlog_dir: Path,
    name: str,
    *,
    context: str | None = None,
    outcome: str | None = None,
    criteria: list[str] | None = None,
) -> str:
    available = templates(backlog_dir)
    try:
        body = available[name]
    except KeyError as exc:
        choices = ", ".join(sorted(available))
        raise ValidationError(f"unknown template {name!r}; available templates: {choices}") from exc

    replacements = {
        "## Context\n\n": context,
        "## Desired outcome\n\n": outcome,
        "## Acceptance criteria\n": (
            "\n".join(f"- {item}" for item in criteria) + "\n" if criteria else None
        ),
    }
    for heading, value in replacements.items():
        if value is not None and heading in body:
            body = body.replace(heading, f"{heading}{value}\n", 1)
    return body.rstrip()


def create_tasks(backlog_dir: Path, task_data: list[dict[str, Any]]) -> list[Task]:
    """Create a batch of tasks, leaving no partial batch behind on failure."""
    validate_backlog(backlog_dir)
    if not task_data:
        raise ValidationError("batch must contain at least one task")

    next_number = max((int(task.id[1:]) for task in list_tasks(backlog_dir)), default=0) + 1
    timestamp = now_iso()
    prepared: list[tuple[Task, Path]] = []
    allowed = {"title", "release", "priority", "size", "state", "tags", "body"}
    for position, values in enumerate(task_data, start=1):
        if not isinstance(values, dict):
            raise ValidationError(f"batch task {position} must be an object")
        unexpected = sorted(set(values) - allowed)
        if unexpected:
            raise ValidationError(f"batch task {position} has unknown fields: {', '.join(unexpected)}")
        task = Task(
            id=f"T{next_number + position - 1:04d}",
            title=values.get("title", "").strip() if isinstance(values.get("title", ""), str) else "",
            release=values.get("release"),
            priority=values.get("priority", 3),
            size=values.get("size"),
            state=values.get("state", "todo"),
            created=timestamp,
            done=timestamp if values.get("state", "todo") == "done" else None,
            tags=normalize_tags(values.get("tags")),
            body=values.get("body", "").strip("\n") if isinstance(values.get("body", ""), str) else values.get("body", ""),
        )
        try:
            task.validate()
        except ValidationError as exc:
            raise ValidationError(f"batch task {position}: {exc}") from exc
        prepared.append((task, backlog_dir / "tasks" / f"{task.id}-{slugify(task.title)}.md"))

    created: list[Path] = []
    try:
        for task, path in prepared:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(serialize_task(task))
            created.append(path)
    except OSError as exc:
        for path in created:
            path.unlink(missing_ok=True)
        raise ConflictError(f"could not create batch atomically: {exc}") from exc
    return [task for task, _ in prepared]


def update_task(
    backlog_dir: Path,
    task_id: str,
    *,
    title: str | object = MISSING,
    release: str | None | object = MISSING,
    priority: int | object = MISSING,
    size: str | None | object = MISSING,
    state: str | object = MISSING,
    tags: list[str] | object = MISSING,
    body: str | object = MISSING,
    expected_revision: str | None = None,
) -> Task:
    path = _find_task_path(backlog_dir, task_id)
    original = path.read_text(encoding="utf-8")
    if expected_revision is not None:
        actual = hashlib.sha256(original.encode("utf-8")).hexdigest()
        if actual != expected_revision:
            raise ConflictError("task changed since it was opened; reload it before saving")
    task = parse_task(original, path.name)
    if task.id != normalize_id(task_id):
        raise ValidationError(f"{path.name}: id does not match its filename")

    if title is not MISSING:
        if not isinstance(title, str):
            raise ValidationError("title must be text")
        task.title = title.strip()
    if release is not MISSING:
        if release is not None and not isinstance(release, str):
            raise ValidationError("release must be text or null")
        task.release = release.strip() if release is not None else None
    if priority is not MISSING:
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValidationError("priority must be an integer")
        task.priority = priority
    if size is not MISSING:
        if size is not None and not isinstance(size, str):
            raise ValidationError("size must be text or null")
        task.size = size
    if tags is not MISSING:
        task.tags = normalize_tags(tags)
    if body is not MISSING:
        if not isinstance(body, str):
            raise ValidationError("Markdown body must be text")
        task.body = body.strip("\n")
    if state is not MISSING and state != task.state:
        if not isinstance(state, str):
            raise ValidationError("state must be text")
        task.state = state
        task.done = now_iso() if state == "done" else None
    task.validate()
    _atomic_write(path, serialize_task(task))
    return task


def check_backlog(backlog_dir: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    try:
        validate_backlog(backlog_dir)
    except BacklogError as exc:
        return [{"file": CONFIG_NAME, "error": str(exc)}]

    seen: dict[str, str] = {}
    for path in sorted((backlog_dir / "tasks").glob("*.md")):
        try:
            task = parse_task(path.read_text(encoding="utf-8"), path.name)
            if not (path.name == f"{task.id}.md" or path.name.startswith(f"{task.id}-")):
                raise ValidationError("id does not match its filename")
            if task.id in seen:
                raise ValidationError(f"duplicate id also used by {seen[task.id]}")
            seen[task.id] = path.name
        except (OSError, BacklogError) as exc:
            issues.append({"file": path.name, "error": str(exc)})
    return issues


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


GENERATED_README = """# Project backlog

This directory is the project's source-of-truth backlog. Each task is one Markdown
file in `tasks/`, with a small YAML front matter header and a free-form body.

Common commands:

```console
backlog add "Describe the task"
backlog add "Describe the task" --template standard --context "Why now" --criteria "It is tested"
backlog add "Fix regression" --tag bug --tag web
backlog upgrade
backlog add-batch --file tasks.json --json
backlog list
backlog show T0001
backlog update T0001 --state in_progress
backlog update T0001 --state done
backlog check
backlog web
```

Metadata rules:

- `release` is `next`, `null`, or any release string.
- `priority` is the release ordering mechanism: `1` required, `2` important,
  `3` normal/default, `4` can move later, `5` parked idea. Do not use unique
  numbers to simulate a manually ordered list.
- `size` is `S` for an isolated, readily testable change; `M` for related changes
  in one layer; `L` for a cross-cutting feature or new app; `null` when it is not
  understood yet. Work larger than `L` is usually a release theme—split it.
- `state` is `todo`, `in_progress`, or `done`. Keep most work in `todo`, normally
  only one main task (occasionally two) in `in_progress`, and use `done` only after
  tests, documentation, and manual validation are complete.
- The body is free-form Markdown.
- `tags` is an optional ordered list of short labels, such as `["bug", "ios"]`.
  Omit it when a task does not need categorization; `list --tag TAG` is repeatable
  and requires every requested tag.

Prefer the CLI or local web app for changes so IDs, timestamps, and validation stay
consistent. The files remain intentionally readable and editable without the tool.

`backlog/.version` records the Personal Backlog version that last generated or
upgraded this integration. It is tracked alongside the backlog and is separate from
the `schema` value in `backlog.toml`. Run `backlog upgrade` to preview generated
README/AGENTS updates, then `backlog upgrade --apply` to write them and refresh the
version marker. On an interactive terminal, the preview ends with `Apply now? [y/N]`.

## Turning conversation context into backlog tasks

Ask an AI agent to read `AGENTS.md` before extracting context. The agent should
inspect existing tasks, update rather than duplicate them, and create one task per
independently actionable outcome. The task body should summarize why the work
exists, its desired outcome, established decisions and constraints, current
progress, and the next useful action. It should not copy an entire transcript.
"""


GENERATED_AGENTS = """# Backlog instructions for AI agents

The Markdown files in `tasks/` are the project's backlog and source of truth.

## Normal workflow

1. Run `backlog list --json` before planning or changing tasks. `--toon` is also
   available when compact LLM context is more useful than JSON interoperability.
2. Inspect likely matches with `backlog show ID --json`.
3. Update an existing task instead of creating a duplicate.
4. Create tasks with `backlog add TITLE` and update them with `backlog update ID`.
5. `add` accepts `--release`, `--priority 1` through `5`, `--size S|M|L|none`,
  `--state`, repeatable `--tag TAG`, and either `--body`, `--body-file PATH`, or `--template NAME`.
   Use `--context`, `--outcome`, and repeatable `--criteria` to fill a template.
6. For scripts, pass `--json` or `--toon` to `add` and `update`; their output is
   the final task object. `add-batch --file PATH` reads an atomic JSON task list.
   `list --tag TAG` is repeatable and returns tasks carrying every requested tag.
7. Finish with `backlog check` and report the task IDs changed.
8. Use `backlog upgrade` to preview generated integration updates. It writes only
   with `--apply` (or an interactive `Apply now? [y/N]` confirmation) and refreshes
   the tracked `backlog/.version` marker last.

Examples:

```console
backlog add "Add offline cache" --release next --priority 1 --size M \
  --template standard --context "The app needs offline reads" \
  --outcome "Cached data remains available" --criteria "Offline launch works" --json
backlog update T0001 --title "Add resilient offline cache" --release next --priority 2 \
  --size M --state in_progress --body "## Current state\n\nStarted" --toon
```

## Extracting context from a conversation

When asked to dump, capture, or remember conversation context, do not copy the
transcript wholesale. Convert it into durable, actionable backlog information:

- Create one task per independently actionable outcome.
- Preserve why the task exists and what successful completion looks like.
- Preserve decisions, rejected alternatives, constraints, and known risks.
- Record current progress and the next useful action.
- Include relevant file paths, links, commands, or error messages.
- Omit greetings, repetition, speculative ideas not adopted, and conversational filler.
- Never store credentials, tokens, private keys, or unrelated personal information.
- Clearly label uncertainty; do not turn guesses into established facts.

Suggested Markdown body headings are `Context`, `Desired outcome`, `Decisions and
constraints`, `Current state`, and `Notes`. Use only the headings that add value.

## Format invariants

- Never change an existing task's `id` or `created` timestamp.
- When setting `state` to `done`, set `done` to the current ISO 8601 timestamp.
- When reopening a task, set `done` to `null`.
- Keep task context and decisions in the free-form Markdown body.
- Do not introduce sprint, assignee, label, or dependency metadata into the header.
- Run `backlog check` after any direct file edit.

## Side-project conventions

- Use priority `1` for work required for its assigned release, `2` for important
  release work, `3` for normal work, `4` for a candidate that can move later, and
  `5` for a parked idea. Priorities are buckets, not a substitute for drag ordering.
- Size `S` is isolated and readily testable; `M` is multiple related changes in one
  layer; `L` is cross-cutting or a new app; `null` means insufficiently understood.
  Split work that grows beyond `L`.
- Keep most tasks in `todo`; normally have one main `in_progress` task, occasionally
  two. Mark `done` only after tests, documentation, and manual validation. No sprint
  ceremony is needed.

Use `backlog --help` for the complete command reference.
"""
