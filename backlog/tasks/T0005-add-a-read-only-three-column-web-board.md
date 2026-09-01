---
id: "T0005"
title: "Add a read-only three-column web board"
release: "next"
priority: 2
size: "M"
state: "done"
created: "2026-08-13T21:35:11+02:00"
done: "2026-08-13T23:12:35+02:00"
---

## Context

The backlog model is deliberately small, and a Trello-like overview should make its three states easier to scan without weakening Markdown and the CLI as the source of truth.

## Desired outcome

Add a local read-only board with Todo, In progress, and Done columns. Cards show the compact task metadata that already exists, including release and size.

## Decisions and constraints

Keep the first iteration read-only. Isolate it from the existing write-capable web editor and current CLI behavior: use a separate server module and static assets, with only a thin command registration in the CLI. Keep the Python runtime dependency-free and bind only to localhost.

The public command is `backlog web`. Root help distinguishes this read-only dashboard from the existing `backlog serve` read/write editor. The temporary `backlog board` name is not retained as an alias.

## Completed

Added `backlog web` on its own default port, a separate GET-only server and static bundle, fixed Todo/In progress/Done lanes, release filtering, refresh, responsive horizontal lanes, and compact release/size/priority cards. The existing `backlog serve` editor is unchanged.

## Validation

The full 24-test suite passes, including assertions for the root help descriptions. JavaScript syntax checking passes. A wheel and source distribution build successfully with the board assets included. A live CLI smoke test returned the dogfood tasks from `GET /api/tasks` and returned HTTP 405 for `POST /api/tasks`.
