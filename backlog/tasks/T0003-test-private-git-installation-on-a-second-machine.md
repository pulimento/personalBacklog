---
id: "T0003"
title: "Test private Git installation on a second machine"
release: "0.8.0"
priority: 2
size: "S"
state: "done"
created: "2026-07-13T20:10:23+02:00"
done: "2026-08-28T17:55:27+02:00"
---

## Context

The repository is private at `pulimento/personalBacklog` and version `v0.1.0` is tagged. Local editable and wheel installs have been verified.

## Desired outcome

Verify that SSH authentication and `uv tool install git+ssh://...@v0.1.0` work from a clean second machine.

## Notes

Record any authentication or upgrade friction before adding a private package registry.
