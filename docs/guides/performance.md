# Performance guide

Budget: 512MB RAM, 0.1 vCPU (Koyeb free tier) - see
`docs/design-log/architecture-design-phase1.md` §2 for the full
constraint table this design targets.

## What's already addressed in the bootstrap

- **No unbounded state.** Every cache is a bounded `TTLCache`
  (`cache/ttl_cache.py`) - this is what replaces the reference bots'
  unbounded global dicts, which is what forced a daily `os.execl`
  process restart as a memory-leak workaround. There is no equivalent
  restart in this design because there's no equivalent leak to work
  around.
- **Plugin/adapter construction cost is paid once**, at startup, not per
  request - `server.py` resolves each provider once and holds it as a
  singleton for the process lifetime.
- **Env-disabled plugins are never imported** - zero RAM, zero startup
  time cost, for optional/heavy plugins (`PLUGINS_DISABLED`).
- **Runtime feature-flag checks are cache reads**, not database
  round-trips, once a flag has been read once (`FeatureFlagService`).
- **Minimal runtime dependencies** - `pyproject.toml` currently declares
  only `aiohttp`. Every additional dependency is added only when the
  feature that needs it is implemented, specifically to avoid the
  reference bots' 50+ package `requirements.txt` (slower cold starts,
  more RAM at idle, larger Docker image).
- **Slim, multi-stage Docker image** (`Dockerfile`) instead of a full
  `python:3.10` base image with the whole `pip install` layer baked in.

## What Phase 3+ needs to get right (not yet implemented, flagged here so
it isn't lost)

- Telegram API calls go through `TelegramGateway`, cache-first, always -
  see `docs/architecture/overview.md`'s ports table. No plugin should
  ever get a raw client reference to bypass this.
- The `telegram` `StorageProvider` adapter's `get_range()` must never
  buffer a full file in memory - constant memory per stream regardless of
  file size, using the concurrent block-prefetch design in
  `docs/design-log/architecture-design-phase1.md` §4.3.
- Search/database adapters should be constructed once and reused - no
  per-request client construction.
