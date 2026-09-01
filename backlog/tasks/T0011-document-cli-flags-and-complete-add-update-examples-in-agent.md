---
id: "T0011"
title: "Document CLI flags and complete add/update examples in AGENTS.md"
release: null
priority: 3
size: "S"
state: "done"
created: "2026-08-17T22:55:10+02:00"
done: "2026-08-28T23:37:11+02:00"
---

## Context
The current AGENTS.md only mentions basic invocation `backlog add TITLE` and `--body-file`, omitting common metadata flags (`--priority`, `--size`, `--body`, `--state`, `--release`). This forces agents to run `backlog add --help` to discover valid values and inline options.

## Desired outcome
Update AGENTS.md in the tool's template/documentation with clear and complete examples of `backlog add` and `backlog update` using common inline flags (`--priority`, `--size`, `--body`, etc.).

## Acceptance criteria
- AGENTS.md includes usage examples with all common flags.
- Allowed values for `--priority` (1-5) and `--size` (S, M, L, none) are documented.
