## What this changes

## Why

## Checklist
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `mypy src` passes
- [ ] `pytest` passes
- [ ] `lint-imports` passes (no dependency-direction violations)
- [ ] If this adds a plugin: no core file needed to change
- [ ] If this adds a provider: it implements an existing port in
      `domain/interfaces.py` (or this PR proposes a new port, discussed
      in an issue first)
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
