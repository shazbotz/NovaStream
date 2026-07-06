# Architecture overview

Full reasoning and evolution: `docs/design-log/`. This page is the
current-state summary.

## Style

**Ports & adapters (hexagonal) for technical seams, a plugin kernel for
feature seams.** Two different problems:

- *"Swap MongoDB for Meilisearch/S3/a Go streaming service without
  touching application code"* -> a port/adapter problem. One interface,
  one adapter per backend, injected at startup.
- *"Add a Music or Anime module without editing core files"* -> a plugin
  problem. A plugin contract, discovered and loaded at startup.

## Dependency direction

```
plugins  ->  kernel  ->  services  ->  domain (interfaces + models)
                                            ^
adapters (mongo, telegram, s3, ...) --implements--┘
```

- `domain/` imports nothing else in this project.
- `services/` imports only `domain/` - never a concrete adapter.
- `kernel/` imports `services/` and `domain/` - it's the runtime
  scaffolding that bundles services and registries into what plugins
  receive.
- `plugins/*` import only `kernel/` (for `PluginContext`) and, through it,
  `services/` - never a concrete adapter, never another plugin's module.
- `server.py` (composition root) is the only file allowed to import both
  a port interface and a concrete adapter and wire them together.

These rules are enforced by `pyproject.toml`'s `[tool.importlinter]`
contracts (`lint-imports` in CI), not just by convention.

## Ports (domain/interfaces.py)

| Port | Purpose | Available adapters | Status |
|---|---|---|---|
| `SearchProvider` | Queryable, ranked catalog index | `null`, `mongo_text` | `mongo_text` written, unit-tested (codecs), not yet run against live MongoDB |
| `StorageProvider` | Where file **bytes** live | `null`, `telegram` | `telegram` written (`storage_telegram`), **not executable-verified** - no `kurigram` install/live credentials in this environment, same caveat as `telegram_kurigram` |
| `DatabaseProvider` / `Repository` | Where structured **records** live | `memory` (functional, non-persistent), `mongo` | `mongo` written, unit-tested (codecs), not yet run against live MongoDB |
| `StreamingService` | The entire playback surface the Bot/Mini App see | `null`, `signed` | `signed` (`streaming_signed`) written and unit-tested (pure HMAC signing/verification, no external deps) - pair with `storage_telegram` for bytes; see `docs/architecture/streaming.md` |
| `AuthProvider` | Verifies caller identity | `null` | Real adapter (Telegram `initData`, API keys, OAuth) not yet built |
| `MetadataProvider` | Title/poster/rating enrichment | `null` | Real adapter (IMDb, TMDB, ...) not yet built |
| `TelegramGateway` | The only path to the Telegram API | `null`, `kurigram` | `kurigram` written, **not executable-verified** (no test bot/credentials available) - the least-verified piece of this codebase, flagged deliberately |
| `FeatureFlags` | Global/chat/group/user feature toggles | Backed by `Repository` + `TTLCache` | Functional against any `DatabaseProvider` |

"Available adapters" beyond `null`/`memory` require the matching optional
dependency group (`pip install -e ".[mongo]"` / `".[telegram]"`) - see
`.env.example` and `docs/guides/deployment.md`.

`SearchProvider` and `Repository` are deliberately separate: the
repository is the system of record, the search index is a derived,
denormalized view that may live in a different system entirely - see
`docs/design-log/architecture-design-phase1-v3.md` §1.

## Provider plugins vs. feature plugins

- **Provider plugins** (`plugins/providers/*`) register one adapter for a
  port, via `ctx.providers.register(port, name, factory)`. They receive a
  minimal `ProviderContext` - registration only, no services.
- **Feature plugins** (`plugins/features/*`) register commands,
  callbacks, HTTP routes, scheduled jobs, settings, and models, via the
  full `PluginContext`, which includes the already-built core services.

Both are discovered automatically at startup (`kernel/plugin_manager.py`)
by scanning their package for a `plugin` module exposing a `PLUGIN`
instance - no plugin is ever imported by name from core code.

## API-first rule

Bot command handlers and HTTP API route handlers are both required to be
thin: parse transport-specific input, call exactly one `services/*`
method, format transport-specific output. Neither may contain logic the
other can't also reach - this is what lets a future Web Dashboard,
Desktop, or Mobile client become "just another client" later, with zero
duplicated logic.

## Performance constraints this design is built around

Target: Koyeb free tier - 512MB RAM, 0.1 vCPU, one instance, scale-to-zero
after an hour idle, SIGTERM with a ~30s grace period. See
`docs/guides/performance.md` and `docs/guides/deployment.md`.
