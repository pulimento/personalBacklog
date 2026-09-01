---
id: "T0014"
title: "Study a special backlog element for session handoff context"
release: "0.8.0"
priority: 3
size: "M"
state: "todo"
created: "2026-08-26T21:38:45+02:00"
done: null
---

## Context
Sessions need a durable handoff record for status, current position, where work stopped, and important context for the next session. This should be represented in the backlog but treated as a distinct element rather than a regular task.

## Desired outcome
Study and define an implementation for a special handoff element, including its data model, display/listing behavior, and CRUD operations. It should support creating, reading, updating, and deleting handoff records without forcing them into task semantics.

## Decisions and constraints
- Preserve the distinction between actionable tasks and session handoff/context records.
- Cover status, current work, where we left off, and important context.
- Use the existing Markdown-backed storage and CLI/web surfaces where appropriate.

## Current state
Idea captured for investigation; implementation approach and UX/API details are still open.
