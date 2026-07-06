# Deployment guide

## Local development

```bash
pip install -e ".[dev]"
python -m media_platform.server
curl http://localhost:8080/healthz
```

Every provider defaults to a null/in-memory adapter (see `.env.example`),
so this works with zero external credentials.

## Koyeb free tier (primary target)

Constraints this architecture is built around - see
`docs/guides/performance.md` and
`docs/design-log/architecture-design-phase1.md` §2:

| Constraint | Value |
|---|---|
| RAM | 512MB |
| CPU | 0.1 vCPU |
| Instances | 1 free instance per org |
| Regions | Frankfurt or Washington D.C. only |
| Scale-to-zero | after 1h idle |
| Shutdown | SIGTERM, ~30s grace, then SIGKILL |

Because only one free instance is available, every component runs in one
container/process for Phase 1-2 - the plugin/port boundaries are what
let pieces (e.g. streaming) move to a separate deployment later without a
rewrite, not something Phase 1-2 does by default.

Build and run:
```bash
docker build -t media-platform .
docker run -p 8080:8080 --env-file .env media-platform
```

Set real provider env vars (`DATABASE_PROVIDER`, `DATABASE_URL`,
`BOT_TOKEN`, etc.) once the corresponding adapters exist (Phase 3+) -
until then, the bootstrap defaults are the only supported configuration.

## Graceful shutdown

The process handles `SIGTERM`/`SIGINT` (`lifecycle.py`): it stops the
scheduler and disconnects the database before exiting, within Koyeb's
~30s grace window, rather than being hard-killed mid-request.
