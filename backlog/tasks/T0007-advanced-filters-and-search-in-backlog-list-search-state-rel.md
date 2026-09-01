---
id: "T0007"
title: "Advanced filters and search in backlog list (--search, --state, --release, --limit)"
release: "0.9.0"
priority: 3
size: "S"
state: "todo"
created: "2026-08-17T21:32:10+02:00"
done: null
---

## Context
`backlog list` returns all tasks without native fast filtering, requiring pipelines with `grep`, `jq`, or other external tools.

## Desired outcome
Add search and filtering flags to `backlog list`:
- `--search <query>` to search for matches in title and body.
- `--state <state1,state2...>` to filter by state (e.g., `todo,in_progress`).
- `--release <release>` to filter by target version.
- `--limit <n>` and `--sort <field>` to narrow down results.

## Acceptance criteria
- Flags available both in human-readable output and with `--json` / `--toon`.
- Case-insensitive and efficient search.
