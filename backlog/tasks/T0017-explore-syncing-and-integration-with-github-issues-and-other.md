---
id: "T0017"
title: "Explore syncing and integration with GitHub Issues and other git hosting providers"
release: null
priority: 5
size: "M"
state: "todo"
created: "2026-09-02T23:48:35+02:00"
done: null
---

## Context

Users may want two-way or one-way synchronization between local Markdown backlog tasks and issue trackers like GitHub Issues, GitLab Issues, etc.

## Desired outcome

An extensible integration mechanism or CLI sync command to import/export/sync backlog tasks with GitHub Issues and other providers without compromising the local-first Markdown format.

## Decisions and constraints


## Acceptance criteria
- Pluggable provider architecture for issue trackers
- Preserves local-first Markdown files as source of truth or cleanly manages sync conflicts
