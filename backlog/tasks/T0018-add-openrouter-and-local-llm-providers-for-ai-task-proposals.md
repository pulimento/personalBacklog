---
id: "T0018"
title: "Add OpenRouter and local LLM providers for AI task proposals"
release: null
priority: 3
size: "M"
state: "todo"
created: "2026-09-01T19:48:22+02:00"
done: null
---

## Context

The current `backlog add-assistant` uses an Apple Intelligence adapter, which is limited to supported Apple Silicon devices with macOS Apple Intelligence enabled.

## Desired outcome

Add an OpenRouter provider adapter to support cross-platform AI task proposals, allowing users to leverage models hosted on OpenRouter. Additionally, consider support for open-source local models (such as OpenLLaMA, Llama via Ollama or llama.cpp, and OpenAI-compatible endpoints).

## Decisions and constraints

- Keep the proposal-first workflow and strict schema validation independent of the provider.
- Store API keys safely or read them from environment variables (e.g., `OPENROUTER_API_KEY`).
- Allow configuring model names via CLI flags or `backlog.toml`.

## Acceptance criteria

- OpenRouter provider adapter implements the structured task proposal interface.
- CLI allows selecting the provider and model (e.g. `--provider openrouter --model ...`).
- Compatible with generic OpenAI-style endpoints for local runtimes (Ollama, llama.cpp, OpenLLaMA).
