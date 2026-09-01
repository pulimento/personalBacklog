---
id: "T0012"
title: "Add project update/upgrade command for projects using backlog"
release: "0.5.0"
priority: 2
size: "M"
state: "done"
created: "2026-08-18T19:06:41+02:00"
done: "2026-08-28T20:06:56+02:00"
---

## Context
When Personal Backlog evolves or new capabilities are added, projects that already initialized a backlog need a seamless way to update their integrated files, agent instructions, and track installed versions.

## Desired outcome
- Implement a command to update/sync projects already using Personal Backlog (e.g., `backlog update` or dedicated project update command).
- Updates project integration files: `README.md`, `AGENTS.md` snippets/instructions.
- Generates/updates a version tracking file (e.g. `.version`, `.lock`, or metadata storing the version name or commit SHA).

## Decisions and constraints
- Resolve command naming since `backlog update <ID>` currently modifies individual tasks (consider naming alternatives like `backlog upgrade`, `backlog sync`, or sub-routing).
