---
id: "T0013"
title: "Check and implement pip publishing"
release: "1.0.0"
priority: 5
size: "S"
state: "done"
created: "2026-08-18T22:36:11+02:00"
done: "2026-09-02T22:24:14+02:00"
---

## Context
Personal Backlog needs distribution packaging so users can install and update it easily via standard package managers. Homebrew is discarded by now.

## Desired outcome
For this project now: publish versioned Git tags and install directly from the private GitHub repository with `uv tool` (or `pipx`). Keep the GitHub Release workflow as the release record and downloadable wheel/sdist, but don’t make the Release asset the primary installer.

```zsh
uv tool install "git+ssh://git@github.com/pulimento/personalBacklog.git@v0.2.1"
# or
pipx install "git+ssh://git@github.com/pulimento/personalBacklog.git@v0.2.1"
```

Why this is the best fit:

- It matches the GitHub setup and is already documented in `README.md`.
- Tags give a reproducible version boundary; the existing workflow builds and attaches wheel/sdist artifacts to a GitHub Release.
- It avoids operating a public package registry for a small, personal/private tool.
- It is simple to update the release workflow later without maintaining another repository.

I would not add Homebrew now. A custom tap would mean maintaining a second repository and formula version/SHA updates for every release, while still ultimately installing a Python CLI. It becomes worthwhile only if you want a macOS-oriented public install experience and expect other Homebrew users.

Publish to PyPI only if the project is intended to be public and broadly reusable. At that point, make PyPI the primary path (`uv tool install personal-backlog`), use GitHub Actions Trusted Publishing rather than storing a long-lived token, and keep the Git install as a developer/private fallback. PyPA currently recommends Trusted Publishing for supported CI platforms, including GitHub Actions. [PyPA guidance](https://packaging.python.org/en/latest/guides/tool-recommendations/)

So my recommendation is:

1. Keep private GitHub + signed/reviewed release tags.
2. Document `uv tool install git+ssh://…@vX.Y.Z` as the canonical install.
3. Keep GitHub Release wheel/sdist assets for verification/manual install.
4. Defer Homebrew and PyPI until the audience becomes public.

No files or backlog items were changed in this planning pass.
