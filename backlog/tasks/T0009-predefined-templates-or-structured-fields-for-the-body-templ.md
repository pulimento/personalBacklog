---
id: "T0009"
title: "Predefined templates or structured fields for the body (--template)"
release: null
priority: 3
size: "S"
state: "done"
created: "2026-08-17T19:20:01+02:00"
done: "2026-08-28T20:21:01+02:00"
---

## Context
The recommended standard for agents includes fixed sections (`Context`, `Desired outcome`, `Decisions and constraints`, `Acceptance criteria`). Currently, the entire text must be composed manually in each `add`.

## Desired outcome
- Flag `--template <name>` (e.g., `feature`, `bug`, `agent`) to initialize the body with a standard Markdown template.
- Optionally, flags for key components such as `--context`, `--outcome`, `--criteria`.

## Acceptance criteria
- `backlog add --template standard` generates the recommended Markdown structure.
- Ability to configure custom templates in `backlog.toml`.
