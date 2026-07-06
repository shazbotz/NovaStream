# Coding standards

| Concern | Tool | Command |
|---|---|---|
| Formatting + linting | ruff | `ruff check .` / `ruff format .` |
| Type checking | mypy (strict) | `mypy src` |
| Tests | pytest + pytest-asyncio | `pytest` |
| Dependency direction | import-linter | `lint-imports` |
| Pre-commit | pre-commit | `pre-commit install` (runs the above on commit) |

All four run in CI (`.github/workflows/ci.yml`) on every pull request.

## Conventions

- Every public module has a module-level docstring explaining its role
  and, where relevant, a pointer to the architecture doc that motivates
  its design.
- Every error raised across a module boundary is a subclass of
  `domain.errors.PlatformError` - see that module's docstring for why.
- `from __future__ import annotations` at the top of every module (lets
  the codebase use modern type-hint syntax while targeting Python 3.11+).
- Dataclasses over dicts for anything that crosses a function boundary
  more than once.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).

## Test split

- `tests/unit/` - fast, no external dependencies, uses fakes/in-memory
  adapters. Runs on every commit.
- `tests/integration/` - real adapters against disposable real
  infrastructure. Runs on a schedule / pre-release, not every commit.
