# Personal Backlog

A tiny, Git-friendly Markdown backlog for side projects. Tasks live in the
project repository, remain readable without this tool, and can be managed from
the command line, a local browser UI, or an AI coding agent.

There are deliberately no sprints, assignees, labels, databases, accounts, or
remote services. Tool is extremely simple by design.

> The idea is to have something very simple to build a backlog, that moves alongside the code. You (Or your agents) can use it via an easy CLI.

## AI setup (recommended)

After installing the tool, initialize each tracked project with:

```console
backlog init --add-agent-instructions
```

This creates `backlog/` and safely creates or appends a managed pointer in the
project's root `AGENTS.md`. It never replaces existing project instructions and
will not duplicate its managed block. The pointer tells Codex to read the detailed, generated
`backlog/AGENTS.md` and use the `backlog` CLI.

Use this prompt when a conversation contains knowledge worth preserving:

> Read `backlog/AGENTS.md`, then extract the actionable project context from this
> conversation into the backlog. Inspect existing tasks first, update instead of
> duplicating, create one task per independently actionable outcome, preserve
> decisions and rationale in the Markdown body, omit conversational filler and
> secrets, run `backlog check`, and report the task IDs you created or updated.

The root `AGENTS.md` in the Personal Backlog source repository is not installed
into consumer projects and would not be discovered there. What the package does
ship is the template used to generate `backlog/AGENTS.md`; the explicit init flag
adds the missing project-root discovery pointer.

A separately installed Codex skill is sufficient if you want Personal Backlog to
be globally discoverable in Codex without changing every repository, but that is
Codex-specific and is not installed by `pip`. An MCP server would make operations
discoverable across configured MCP clients, at the cost of per-client setup and a
larger runtime surface. For ordinary local coding agents, the generated files and
CLI remain the simplest integration.

## Install

From PyPI with `uv tool` (recommended):

```console
uv tool install personal-backlog
```

Or with `pipx` / `pip`:

```console
pipx install personal-backlog
# or
pip install personal-backlog
```

From GitHub:

```console
uv tool install "git+https://github.com/pulimento/personalBacklog.git@v0.3.3"
```

For local development:

```console
uv tool install --editable .
```

The installed command is `backlog`.

## Start a project backlog

Run this from a pet project's root:

```console
backlog init --add-agent-instructions
backlog add "Add offline cache" --release next --priority 1 --size M
backlog add "Improve import errors"
backlog list
backlog upgrade
backlog web
backlog serve
```

`backlog init` creates:

```text
backlog/
├── backlog.toml
├── README.md
├── AGENTS.md
└── tasks/
```

The CLI searches the current directory and its parents for that backlog, so it
also works from nested project directories. Use `--backlog PATH` to select one
explicitly.

## Commands

```console
backlog init [PATH] [--add-agent-instructions]
backlog upgrade [--apply] [--json | --toon]
backlog add TITLE [--release RELEASE] [--priority 1|2|3|4|5] [--size S|M|L|none] [--tag TAG ...] [--body TEXT | --body-file PATH | --template NAME]
backlog add-batch [--file PATH] [--json | --toon]
backlog add-assistant REQUEST [--provider apple-intelligence] [--apply] [--json | --toon]
backlog list [--state STATE] [--release RELEASE] [--tag TAG ...] [--json | --toon]
backlog show ID [--json | --toon]
backlog update ID [--title TITLE] [--state todo|in_progress|done] [--release RELEASE] [--priority 1|2|3|4|5] [--size S|M|L|none] [--tag TAG ... | --clear-tags] [--body TEXT | --body-file PATH]
backlog check [--json | --toon]
backlog web [--port 8765] [--no-browser] [--read-only]
backlog serve [--port 8765] [--no-browser] [--read-only]
```

Use `none`, `null`, or `-` for an unassigned release. Use `--size none` to clear
a size. Tags are optional: repeat `--tag` for each label (for example, `--tag bug
--tag ios`), and use `--clear-tags` to remove them during an update. Repeat `--tag`
with `backlog list` to require one or more tags. `--body-file -` reads Markdown from standard input, which is convenient
for scripts and agents. `--template standard`, `feature`, `bug`, or `agent`
initializes a Markdown body; `--context`, `--outcome`, and repeatable `--criteria`
fill standard sections. Projects can define additional bodies in `[templates]` in
`backlog.toml`. `--body`/`--body-file` cannot be combined with a template.

`backlog upgrade` previews updates to the generated `backlog/README.md`,
`backlog/AGENTS.md`, and the managed block in the project-root `AGENTS.md`. Run it
with `--apply` to write those updates; on an interactive terminal the preview ends
with `Apply now? [y/N]`. Every initialized or upgraded project tracks
the installed integration version in `backlog/.version`; commit that tiny file with
the rest of the backlog. It is separate from `backlog.toml`'s data schema version.

`backlog add-batch --file tasks.json` creates a JSON array of task objects (or an
object containing only `tasks`) after validating the full batch; if any entry is
invalid, no task is created. Accepted fields are `title`, `release`, `priority`,
`size`, `state`, and `body`. Use `--file -` (the default) to read from stdin.
`add`, `add-batch`, and `update` all accept `--json` or `--toon` to return the
created or final task object(s) for scripts.

### Local AI task proposals

`backlog add-assistant "Add an accessibility audit to the current release, top priority"`
asks the selected provider for one structured, validated task proposal. It is
proposal-only by default: review the result, then repeat the command with
`--apply` only when you want to create the task.

> **Device Compatibility:** The `apple-intelligence` provider runs entirely
> on-device using Apple's Foundation Models framework via a local Swift bridge.
> It requires a supported Apple Silicon device running macOS 15.1+ (Sequoia or later)
> with Apple Intelligence enabled and its local model downloaded. On unsupported
> platforms (Linux, Windows, Intel Macs) or devices without Apple Intelligence,
> this provider is unavailable. No API key or remote AI provider is configured
> by this tool. Other providers can be added behind the same provider interface
> without changing task validation or creation.

`backlog web` opens the local browser UI (binding safely to `127.0.0.1` on port `8765` by default). It includes both an interactive three-column Kanban board (Todo, In progress, Done) and a list/editor workspace, with a quick view switcher in the header. Use `--read-only` (or toggle the read-only switch in the UI) to browse tasks safely without allowing modifications. `backlog serve` is supported as an alias.

When it can determine one, the web app initially selects the earliest release that still has unfinished work; if that calculation is unavailable, it shows all releases. Selecting a card in board view opens its full Markdown details in a dialog; in editor view, selecting a task displays its details in the sidebar where you can edit and save changes. Detects conflicting concurrent edits before saving.

The prompt above intentionally asks for an extraction, not a raw transcript dump.
A backlog task should retain enough context for a future human or agent to continue:

- why the task exists;
- the desired outcome;
- decisions and constraints already established;
- current progress and the next useful action;
- relevant file paths, links, or commands.

The agent can read metadata with `backlog list --json`, or use `--toon` for a more
compact LLM-oriented representation. JSON remains the interoperability format.
TOON renders task tags as one display-only scalar such as `bug · ios` (or `null`
when absent), keeping task lists tabular; JSON and Markdown retain the canonical
array.
Full bodies are available through `backlog show ID --json` or `--toon`; longer
Markdown can be written using `--body-file PATH` or `--body-file -`.

## Releases and packages

The CI workflow tests Python 3.11–3.13 and attaches wheel/source distributions to
each workflow run. The Release workflow runs automatically for every pushed `v*`
tag: it tests the tagged source, verifies that the tag equals the version in
`pyproject.toml`, builds both distributions, creates a GitHub Release with
generated notes, and publishes the package to PyPI via Trusted Publishing.

```console
# First update the version in pyproject.toml and src/personal_backlog/__init__.py
git commit -am "Release 0.3.3"
git tag -a v0.3.3 -m "Personal Backlog 0.3.3"
git push origin main --tags
```

To create the missing GitHub Release for the already-pushed `v0.1.0` tag after
this workflow reaches `main`, open **Actions → Release → Run workflow**, enter
`v0.1.0`, and run it. Releases are published automatically to PyPI and attached
as wheel/sdist assets to GitHub Releases.

## Dogfooding this repository

This repository is itself a tracked project: its live backlog is the `backlog/`
folder. From the repository root, use it exactly like any other project:

```console
backlog list
backlog show T0001
backlog check
backlog web
backlog serve
```

That is the whole dogfood mechanism. Changes made through the CLI or web app are
ordinary Git changes to `backlog/tasks/*.md` and should be reviewed and committed
with the code they describe.

## Task format

Each task is a Markdown file such as `T0001-add-offline-cache.md`:

```markdown
---
id: "T0001"
title: "Add offline cache"
release: "next"
priority: 1
size: "M"
state: "in_progress"
tags: ["bug", "ios"]
created: "2026-07-13T10:30:00+02:00"
done: null
---

## Context

Previously loaded data should remain available offline.
```

The task itself is Markdown with YAML front matter. The parser supports a flat,
intentionally small subset of YAML; JSON-style quoted strings, ordinary unquoted
strings, integers, and `null` are accepted. JSON is only an optional CLI and HTTP
API representation—it is not the on-disk backlog format. TOON is an additional
CLI-only output optimized for compact LLM context; it follows the working-draft
[TOON 3.3 specification](https://toonformat.dev/reference/spec) for the
JSON-shaped values emitted by this tool.

- IDs and creation timestamps never change.
- Priority is a five-bucket release ordering mechanism: `1` required for its
  assigned release; `2` important for it; `3` normal/default; `4` can move later;
  `5` parked idea. Do not use unique priorities to simulate drag ordering.
- Release is `next`, any project-specific release string, or `null`.
- Size `S` is an isolated, readily testable change; `M` is multiple related changes
  in one layer; `L` is a cross-cutting feature or new app; `null` means it is not
  understood yet. Split work that grows beyond `L` into actionable outcomes.
- State is `todo`, `in_progress`, or `done`. Keep most work in `todo`, normally one
  main task (occasionally two) in `in_progress`; use `done` only after tests,
  documentation, and manual validation are complete. No sprint ceremony is needed.
- Completing and reopening tasks maintains the `done` timestamp automatically.
- Tags are optional short labels. A task can have more than one, including `bug`;
  leave them absent when they add no useful context.
- The Markdown body has no required structure.

## Development

The project requires Python 3.11+ and has no runtime dependencies.

```console
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m personal_backlog --help
```

To exercise the checkout without using the globally installed `backlog` command,
run the development launcher. It resolves this repository's `src/` directory and
replaces `PYTHONPATH`, so the current source is always the one executed:

```console
./scripts/backlog-dev --help
./scripts/backlog-dev --backlog ./backlog list
```
