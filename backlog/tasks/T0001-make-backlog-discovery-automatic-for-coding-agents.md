---
id: "T0001"
title: "Make backlog discovery automatic for coding agents"
release: "0.1.0"
priority: 1
size: "S"
state: "done"
created: "2026-07-13T20:46:00+02:00"
done: "2026-07-13T22:08:02+02:00"
---

## Context

A nested `backlog/AGENTS.md` explains task operations, but an agent may not discover the backlog until it is pointed there from the project root.

## Desired outcome

Provide a safe, explicit way to make the backlog discoverable from project-root agent instructions.

## Decisions and constraints

The tool must never silently modify an existing root `AGENTS.md`. A Codex skill remains an optional global integration; MCP is deferred until cross-client tool discovery is needed.

## Result

Implemented `backlog init --add-agent-instructions`. The opt-in flag creates or appends a managed project-root pointer without replacing existing instructions or duplicating its managed block. The README now puts this setup and the conversation-extraction prompt first.
