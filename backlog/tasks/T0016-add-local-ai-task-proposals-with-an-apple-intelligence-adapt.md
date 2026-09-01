---
id: "T0016"
title: "Add local AI task proposals with an Apple Intelligence adapter"
release: "0.9.0"
priority: 2
size: "L"
state: "done"
created: "2026-08-28T23:31:13+02:00"
done: "2026-08-28T23:56:52+02:00"
---

## Context

Creating a well-formed task through many CLI flags is awkward for people. The feature needs a provider abstraction so other local or remote AI runtimes can be added later without changing task creation semantics.

## Desired outcome

Provide backlog add-assistant as a proposal-first workflow, with an Apple Intelligence adapter as the initial provider.

## Decisions and constraints

- Providers return structured proposals only; the core validates them before any write.
- Creation requires explicit --apply.
- The Apple adapter uses the local Foundation Models bridge and does not configure a remote provider or API key.

## Current state

Implementation and automated tests are complete. A real proposal run against a temporary backlog on this Mac reported that Apple Intelligence is unavailable; enable Apple Intelligence and wait for its model download, then rerun the manual check.

## Acceptance criteria

- The default command produces a validated task proposal without writing files
- Only an explicit apply action creates a task
- Apple Intelligence is isolated behind a provider interface
- Future providers can be configured without changing the core proposal or validation path
