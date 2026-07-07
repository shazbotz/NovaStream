# Credits

## Inspirations

This project's architecture draws on engineering patterns studied from
several open-source Telegram bot projects, then redesigned from scratch -
see `docs/architecture/overview.md` for the full reasoning. Specific
techniques carried forward:

- Producer/consumer bulk-indexing pipelines with bounded concurrency
- HTTP range-request streaming with concurrent block prefetching
- Semaphore-bounded broadcast fan-out
- In-Telegram admin panel UX

These are credited as techniques, not as a fork - this project's plugin
architecture, port/adapter interfaces, and feature set were designed
independently. See `architecture-design-phase1.md` for the reference
material reviewed.

## Upstream projects

- [aiohttp](https://github.com/aio-libs/aiohttp) - async HTTP server
- (Additional libraries are added here as they're introduced - see
  `pyproject.toml` for the current dependency list.)

## Contributors

_Populated as people contribute - see `CONTRIBUTORS`._

## Special thanks

{{project.credits.special_thanks}}
