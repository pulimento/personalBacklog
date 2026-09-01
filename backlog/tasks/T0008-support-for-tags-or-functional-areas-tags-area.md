---
id: "T0008"
title: "Support for tags or functional areas (tags / area)"
release: "0.5.0"
priority: 3
size: "M"
state: "done"
created: "2026-08-17T18:13:46+02:00"
done: "2026-08-28T17:12:53+02:00"
---

## Context
Currently, categorization by area or component (e.g., ios, backend, tui, docs) must be inferred from the task title or body.

## Desired outcome
Allow assigning tags or an area to tasks via structured metadata and CLI flag (e.g., `--tags` or `--area`), facilitating filtering by technical domain or project module.

## Acceptance criteria
- Optional field compatible with backlog invariants.
- Ability to filter in `backlog list` by tag/area.
- Compatible with web views and CLI.
