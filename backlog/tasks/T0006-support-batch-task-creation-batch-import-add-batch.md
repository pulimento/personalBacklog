---
id: "T0006"
title: "Support batch task creation (batch import / add-batch)"
release: null
priority: 3
size: "M"
state: "done"
created: "2026-08-17T22:46:05+02:00"
done: "2026-08-28T21:47:26+02:00"
---

## Context
Currently, creating multiple tasks requires invoking `backlog add` sequentially one by one.

## Desired outcome
Allow creating or importing multiple tasks at once via a batch command (e.g., `backlog import` or `backlog add-batch`), accepting a structured document (JSON, YAML, or TOON) via file or stdin.

## Acceptance criteria
- Command processes a list of tasks and creates the corresponding files in `tasks/`.
- Atomic handling or clear reporting of created tasks with their generated IDs.
- Full validation of format invariants for each created task.
