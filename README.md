# {{project.project.name}}

{{project.project.tagline}}

> **Status: Phase 3 in progress.** Real `mongo`/`mongo_text` adapters and
> three feature plugins (`catalog_search` with variant grouping,
> `continue_watching`, `genre_browsing`) are built and tested. `kurigram`
> (Telegram) adapter is written but not verified against a live bot.
> Streaming, Download, Offline Viewing, the Mini App, and a live bot
> polling loop are not started - see `ROADMAP.md` for the exact
> built/written/deferred breakdown and why.

## What this is

A plugin-based, ports-and-adapters Telegram media platform: an
AutoFilter-style search/catalog backend, a Telegram Bot, and a Telegram
Mini App, designed so that the search engine, file storage backend,
database, and streaming engine are all swappable adapters behind stable
interfaces - see `docs/architecture/overview.md` for the full design and
reasoning.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # optional - every setting has a working default
python -m media_platform.server
```

Then, in another terminal:

```bash
curl http://localhost:8080/healthz
```

You should get back a JSON response listing the loaded (bootstrap) providers
and plugins. No database, Telegram bot token, or other external credential
is required to reach this point - every port defaults to a null or
in-memory adapter, on purpose, so the foundation can be verified before any
real infrastructure is wired up. See `docs/guides/deployment.md` for how
that changes once real adapters are configured.

Try the first feature plugin (returns zero results against the default
`null` search adapter, but proves the whole request path works):
```bash
curl "http://localhost:8080/api/search?q=test"
```
See `docs/api/reference.md` for the full route list, and `.env.example`
for switching to the real `mongo`/`mongo_text` adapters.

## Running the tests

```bash
pytest                 # unit tests - fast, no external dependencies
ruff check . && mypy src
lint-imports            # verifies the dependency-direction rules hold
```

## Project layout

```
src/media_platform/
  domain/        interfaces (ports), models, errors - depends on nothing else in this project
  services/       thin orchestration over the domain interfaces
  kernel/         plugin runtime: registries, plugin manager, provider registry
  plugins/
    providers/    adapters for each port (search, storage, database, auth, metadata, streaming, telegram)
    features/     user-facing functionality (empty until Phase 3+)
  server.py       composition root - the only file that wires a concrete adapter to an interface
miniapp/          separate frontend project (Telegram Mini App)
docs/             architecture docs, guides, API reference
tests/            unit (fast, fakes only) and integration (real adapters, Phase 3+)
```

See `docs/architecture/overview.md` for why it's shaped this way, and
`docs/guides/plugin-development.md` for how to extend it.

## Documentation

- [Architecture overview](docs/architecture/overview.md)
- [Plugin development guide](docs/guides/plugin-development.md)
- [Contributing](CONTRIBUTING.md)
- [Deployment guide](docs/guides/deployment.md)
- [Performance guide](docs/guides/performance.md)

## License

Apache-2.0 (decided in Phase 3 - see `LICENSE` for the reasoning and
`docs/design-log/open-source-project-structure.md` §7 for the original
tradeoff comparison). **The `LICENSE` file currently contains a notice
and the standard short header, not the full ~201-line legal text** -
copy that from https://www.apache.org/licenses/LICENSE-2.0.txt before
publishing (see `LICENSE` for why it wasn't reconstructed from search
snippets here).

## Credits

See `CREDITS.md`.
