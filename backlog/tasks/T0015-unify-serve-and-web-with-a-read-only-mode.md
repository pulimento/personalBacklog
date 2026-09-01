---
id: "T0015"
title: "Unify serve and web with a read-only mode"
release: "0.9.0"
priority: 2
size: "L"
state: "done"
created: "2026-08-28T23:21:51+02:00"
done: "2026-09-02T17:14:07+02:00"
---

## Context

The current serve editor and web board duplicate much of the same task browsing and detail experience, yet are maintained as separate web applications.

## Desired outcome

Provide one local web application with distinct board and editor views, plus a read-only mode switch, while preserving the existing safety and local-only behavior.

## Decisions and constraints


## Acceptance criteria
- Both entry points use one shared frontend and HTTP surface
- The UI can switch between board and editor views without a separate server
- Read-only mode prevents task mutations and clearly communicates that state
- Existing deep links, current-release default selection, and task-detail behavior remain covered by tests
