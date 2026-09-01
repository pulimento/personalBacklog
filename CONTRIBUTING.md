# Contributing to Personal Backlog

Thank you for your interest in contributing to Personal Backlog!

## Development Setup

The project requires Python 3.11+ and has zero runtime dependencies.

1. Clone the repository:
   ```console
   git clone https://github.com/pulimento/personalBacklog.git
   cd personalBacklog
   ```

2. Run the test suite:
   ```console
   PYTHONPATH=src python3 -m unittest discover -s tests -v
   ```

3. Run the development CLI launcher:
   ```console
   ./scripts/backlog-dev --help
   ```

## Guidelines

- **Zero dependencies:** Keep the core runtime zero-dependency. Do not introduce third-party Python packages.
- **Tests:** Add unit tests for any new features, bug fixes, or behavioral changes in `tests/`. Ensure all tests pass before submitting.
- **Dogfooding:** This repository uses its own `backlog/` for task tracking. Run `PYTHONPATH=src python3 -m personal_backlog check` after updating tasks.
- **Pull Requests:** Keep changes focused, surgical, and well-described.
