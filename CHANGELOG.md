# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/), versioning follows
[Semantic Versioning](https://semver.org/) - see
open-source-project-structure.md §6.

## [Unreleased]

### Added (Phase 4 - Streaming backend + Mini App core screens)
- `services/stream_tokens.py`: pure HMAC-SHA256 signed/expiring URL
  scheme (`sign`/`verify`), 7 unit tests.
- `services/range_parsing.py`: HTTP `Range` header parser extracted from
  the new `/stream` handler (explicit/open-ended/suffix ranges,
  multi-range rejection, 416 cases), 13 unit tests.
- `streaming_signed` provider plugin (`STREAMING_PROVIDER=signed`): real
  `StreamingService` adapter issuing the signed URLs above. 3 unit tests.
- `storage_telegram` provider plugin (`STORAGE_PROVIDER=telegram`): real
  `StorageProvider` adapter reading file bytes from Telegram via a
  dedicated, lazily-connecting kurigram client pool
  (`plugins/providers/storage_telegram/client.py`), separate from the
  bot-core `TelegramGateway`. Not executable-verified - see its
  docstring; `RemoteFileRef` payload parsing (the one dependency-free
  piece) has 4 unit tests.
- `streaming` feature plugin: authenticated `GET /api/stream-token/{id}`
  and `GET /api/download-token/{id}`, 5 unit tests.
- Raw `/stream/{media_id}` HTTP handler, registered directly by
  `server.py` next to `/healthz` (outside `ApiRouter`, which is
  JSON-only by design): verifies the signed URL, serves bytes from
  `StorageProvider` with `Range` support (206/416), and sends
  `Content-Disposition: attachment` for downloads - one endpoint powers
  both Streaming and Download/Offline Download.
- New `Settings` fields: `stream_secret`, `public_base_url`,
  `stream_url_expiry_seconds`, `stream_chunk_size`,
  `stream_worker_tokens` - all optional, bootstrap defaults unaffected.
- Mini App (`miniapp/`): React + Vite + TypeScript + Tailwind. Search,
  Browse (genre grid + per-genre list), Media Details (variant
  selection), Player (native `<video>`, resumes via
  `continue_watching`, reports progress) pages; shared UI components
  (`Header`, `BottomNav`, `MediaCard`, loading/error states); an
  in-memory navigation stack (`lib/navigation.ts`); an API client
  (`lib/api-client.ts`) and a Telegram `initData`/back-button/haptics
  wrapper (`lib/telegram.ts`). Not run through `npm install`/`tsc`/a
  browser (no network in the build environment) - source syntax-checked
  and bundle-resolution-checked with `esbuild` against a real,
  separately obtained React instead. See `miniapp/README.md`.
- `docs/api/reference.md` and `docs/architecture/streaming.md` /
  `overview.md` updated to describe the routes and adapters above.

### Fixed (Phase 4)
- `tests/unit/test_bootstrap.py` and `test_plugin_manager.py`: updated
  the hardcoded discovered-provider-plugin counts/lists (7 -> 9) now that
  `streaming_signed` and `storage_telegram` exist - not a behavior change,
  just the test catching up to two legitimately new provider plugins.

### Added (Phase 3b - Catalog Variant Grouping + two more plugins)
- **Catalog Variant Grouping** in `catalog_search`: search results group
  multiple file variants of the same movie/series (by normalized title +
  release year) into one entry with a variant list (language, quality,
  codec, release type, file size), instead of one row per file.
  Single-variant titles skip the selection step. Presentation-layer only
  - `plugins/features/catalog_search/grouping.py`, 10 unit tests.
- `CatalogItem` gained `codec`, `release_type`, `year`, and `genres`
  fields, needed for grouping and genre browsing. Mongo codecs and
  `POST /api/media`'s request parsing updated to match.
- `continue_watching` feature plugin: authenticated
  `GET /api/continue-watching` / `POST /api/watch-progress`, deriving
  `user_id` from the authenticated principal rather than trusting a
  client-supplied value.
- `genre_browsing` feature plugin: `GET /api/genres/{genre}`.
- `services/auth_helper.py`: shared `require_authenticated`/
  `bearer_credentials` helpers, extracted after the same authenticate-or-
  401 logic appeared in a second plugin.
- `CatalogService.list_by_genre()`.
- `kernel/api_router.py`: `parse_query_int()`, shared pagination-param
  parsing used by every plugin that paginates.

### Fixed (Phase 3b)
  `genres`) the same way MongoDB natively does (`{"genres": "Action"}`
  matching a document whose `genres` array contains `"Action"`) - previously
  it only supported exact equality, which would have made genre browsing
  behave differently depending on which `DatabaseProvider` was active.
- A layering violation caught before shipping: an early draft of
  `services/auth_helper.py` took an HTTP-specific `ApiRequest` parameter,
  which would have made `services/` depend on `kernel/` - forbidden by
  this project's own `[tool.importlinter]` contracts. Fixed by having the
  helper take a transport-agnostic `Credentials` object instead, with the
  HTTP-specific header extraction (`bearer_credentials`) kept separate.
- `normalize_title()` (grouping) originally *removed* punctuation instead
  of replacing it with a space, so `"Iron-Man"` normalized to `"ironman"`
  instead of `"iron man"` and failed to group with `"Iron Man"` - caught
  by actually running the test, not by review.

### Notes
- No feature plugins beyond `catalog_search`, `continue_watching`, and
  `genre_browsing` yet. Streaming, Download, Offline Viewing, the Mini
  App, and a live Telegram bot polling loop remain not started - see
  `ROADMAP.md` for exactly what's built vs. written-but-unverified vs.
  not attempted, and why.
- License decided: Apache-2.0 (see `LICENSE` for reasoning). The
  `LICENSE` file has the decision and the standard short header, but not
  the full legal text yet - copy that from the canonical source before
  publishing (see `LICENSE`'s own notice for why).

---

### Added (Phase 3a - Mongo adapters + first feature plugin)
- Real `mongo` `DatabaseProvider` adapter (motor-based), with unit-tested
  document codecs for `CatalogItem`, `FeatureFlag`, and `WatchProgress`.
- Real `mongo_text` `SearchProvider` adapter, using a native MongoDB
  `$text` index - see `docs/architecture/search.md`.
- `kurigram`-backed `TelegramGateway` adapter for outbound Telegram API
  calls (membership checks, reading/sending messages). Written but not
  yet integration-tested against a live bot - see its module docstring.
- First feature plugin, `catalog_search`: `GET /api/search`, an
  authenticated `POST /api/media`, and a transport-agnostic `search` bot
  command, all backed by one `CatalogService`.
- `ApiRequest`/`ApiResponse` types (`kernel/api_router.py`) so feature
  plugins never need to import aiohttp - `server.py` is now the only
  place that touches aiohttp types, with error-to-HTTP-status mapping
  centralized there.
- `config: Settings` on `ProviderContext` so provider plugins can read
  connection strings/credentials, and `auth: AuthProvider` on
  `ServiceLocator` so feature plugins can authenticate callers.
- `connect()`/`disconnect()` added to the `TelegramGateway` interface,
  symmetric with `DatabaseProvider`, wired into startup/graceful shutdown.

### Fixed (Phase 3a)
- `kernel/plugin_manager.py`: a provider plugin whose own dependency
  (e.g. `motor`) isn't installed was previously indistinguishable from
  "this subpackage isn't a plugin" - both hit `ModuleNotFoundError` and
  were silently skipped. Now the missing-dependency case logs a clear
  warning and is skipped without crashing discovery of every other
  plugin; a plugin that fails for any other reason still raises loudly.
- A cross-plugin import (`search_mongo_text` importing from
  `database_mongo` directly) was moved to a shared, non-plugin support
  module (`plugins/providers/_mongo_shared/`) instead.

### Added (Phase 2 - project bootstrap)
- Project foundation: domain layer (models, port interfaces, error
  hierarchy), plugin kernel (registries, plugin manager, provider
  registry), bootstrap provider plugins (null/in-memory adapters for
  every port), configuration system, structured logging, application
  lifecycle (graceful shutdown), composition root, and test scaffolding.
- No feature plugins yet at this point - that release was infrastructure
  only.
