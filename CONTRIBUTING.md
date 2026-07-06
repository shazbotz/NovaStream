# Contributing

Thanks for considering contributing. This project is structured
specifically to make contribution straightforward - see
`docs/architecture/overview.md` for the design and
`docs/guides/plugin-development.md` if you're adding a feature or
provider.

## Getting started

```bash
git clone {{project.project.repository_url}}
cd media-platform
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
pytest
```

If `pytest` passes with no errors, your environment is set up correctly -
the bootstrap project ships with only null/in-memory adapters, so no
external database or Telegram credentials are required to run the test
suite.

## Before opening a pull request

- `ruff check .` and `ruff format .` - formatting/linting
- `mypy src` - type checking
- `pytest` - unit tests (fast, no external dependencies)
- `lint-imports` - verifies the dependency-direction rules in
  `pyproject.toml`'s `[tool.importlinter]` section aren't violated

All of the above run in CI (`.github/workflows/ci.yml`) on every pull
request.

## Adding a feature

Features are plugins - see `docs/guides/plugin-development.md`. In short:
create a new directory under `src/media_platform/plugins/features/`,
expose a `PLUGIN` instance in a `plugin.py` module, and register whatever
you need (commands, routes, jobs, settings, models) through the
`PluginContext` passed to `register()`. No core file needs to change.

## Adding a provider adapter

Same mechanism, under `src/media_platform/plugins/providers/`, registering
an implementation of one of the port interfaces in
`src/media_platform/domain/interfaces.py` via `ctx.providers.register(...)`.

## Commit style

This project uses [Conventional Commits](https://www.conventionalcommits.org/)
so `CHANGELOG.md` can be generated from commit history - see
open-source-project-structure.md §6.

## Code of conduct

Participation in this project is governed by `CODE_OF_CONDUCT.md`.
