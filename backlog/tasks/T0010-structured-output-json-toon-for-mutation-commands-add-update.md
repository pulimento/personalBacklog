---
id: "T0010"
title: "Structured output (JSON/TOON) for mutation commands (add, update)"
release: null
priority: 3
size: "S"
state: "done"
created: "2026-08-17T21:44:47+02:00"
done: "2026-08-28T20:00:00+02:00"
---

## Context
`backlog add` and `backlog update` output plain text confirmations (e.g., `Created T0006: ...`), which complicates automated parsing by agents and scripts without text processing.

## Desired outcome
Support `--json` and `--toon` in mutation commands like `add` and `update`, returning the newly created or modified task as a structured object.

## Acceptance criteria
- `backlog add "..." --json` returns the created task object with its ID, timestamps, and properties.
- `backlog update ID ... --json` returns the final state of the task after mutation.
