# Roadmap

This tracks the project's phased build-out. See `docs/architecture/`
for the full design behind each phase.

## Phase 1 - Architecture design (complete)
Ports & adapters + plugin kernel design, feature-flag system, dependency
rules, open-source project structure.

## Phase 2 - Project bootstrap (this release)
Domain layer, core interfaces, plugin kernel, composition root,
configuration, logging, error handling, lifecycle, bootstrap
(null/in-memory) provider adapters, test scaffolding. No feature plugins
yet - see `docs/architecture/overview.md`.

## Phase 3 - First functional module (complete)

**Built and tested (unit tests, no live infrastructure needed):**
- Real `DatabaseProvider`/`Repository` adapter (`mongo`, via motor) - full
  CRUD against MongoDB, with unit-tested (de)serialization codecs.
- Real `SearchProvider` adapter (`mongo_text`) - native MongoDB `$text`
  index, replacing the reference bots' infix-regex full-collection-scan.
- `catalog_search` plugin: `GET /api/search` (results grouped by
  title+year - see "Catalog Variant Grouping" below), authenticated
  `POST /api/media`, and a transport-agnostic `search` bot command.
- **Catalog Variant Grouping** (`plugins/features/catalog_search/grouping.py`):
  multiple file variants of the same movie/series (different
  language/quality/codec/release) now show as one search result with a
  variant list, not one row per file. Single-variant titles skip straight
  to details instead of prompting a selection step. Presentation-layer
  only - no changes to `SearchProvider`, `StorageProvider`,
  `StreamingService`, or the plugin architecture, per this enhancement's
  own constraint. 10 unit tests.
- `continue_watching` plugin: authenticated `GET /api/continue-watching` /
  `POST /api/watch-progress`, deriving `user_id` from the authenticated
  principal (never a client-supplied value - see its plugin docstring for
  why that matters).
- `genre_browsing` plugin: `GET /api/genres/{genre}`.
- `services/auth_helper.py`: shared authenticate-or-401 logic, extracted
  after duplicating it once (see CHANGELOG for a layering bug this caught
  along the way).
- A real fix to plugin discovery: a provider plugin whose dependency
  (`motor`, `kurigram`) isn't installed is now skipped with a clear
  warning instead of crashing the whole application or silently vanishing
  indistinguishably from "this isn't a plugin."

**Written, not yet verified against live infrastructure** (no network
access to install `motor`/`kurigram` or reach a real MongoDB/Telegram in
the environment this was built in - see each file's own docstring):
- `KurigramTelegramGateway` (outbound Telegram API calls: membership
  checks, reading messages, sending messages).

**Deferred to Phase 4 at the time, since built there (see below):**
Streaming/Download/Offline Viewing plugins and the Mini App - the real
`StorageProvider`(telegram)/`StreamingService` adapters and the
JS/TypeScript frontend both needed either a live bot token or explicit
sign-off to receive as written-but-unrun code; both were taken up and
built in Phase 4 below.

**Explicitly not attempted, and why (see the chat record for the full
reasoning rather than repeating it here):**
- **Broadcast, Statistics, Notifications, Admin Dashboard, Inline Search,
  Channel Access** - each achievable with the same pattern as the plugins
  above (no live infrastructure required for most of them), just not
  reached in this pass. Notes on what each needs:
  - `broadcast`: fan-out over `TelegramGateway.send_message`, semaphore-
    bounded (reuse the concurrency pattern from
    `docs/design-log/architecture-design-phase1.md` §1) - fully buildable
    and testable now with a fake gateway.
  - `statistics`: needs a decision on exact vs. approximate counts (an
    exact catalog size needs a COUNT-style Repository operation that
    doesn't exist yet - see `CatalogService.list_by_genre`'s docstring for
    the same tension around DISTINCT).
  - `notifications`: same shape as broadcast, narrower (single
    user/topic) - buildable now.
  - `admin_dashboard`: the in-Telegram UI needs the (deferred) bot polling
    loop; the underlying settings-storage problem (persisting
    admin-edited values, not just declared defaults) isn't solved yet
    either - `SettingsRegistry` today only holds declarations.
  - `inline_search`/`channel_access`: see the chat record - both are
    thin/low-value without infrastructure that doesn't exist yet (a live
    bot for inline_search; admin-editable settings storage for
    channel_access's required-chat-list).

## Phase 4 - Streaming backend + Mini App core screens (this release)

**Built and unit-tested (no live infrastructure needed):**
- `services/stream_tokens.py`: pure HMAC-SHA256 signed/expiring URL
  scheme (sign + constant-time verify), shared by the adapter that
  issues URLs and the handler that checks them.
- `services/range_parsing.py`: HTTP `Range` header parsing (explicit
  range, open-ended, suffix ranges, multi-range rejection, 416 cases) -
  extracted from the `/stream` handler so it's unit-testable without
  aiohttp.
- `streaming_signed` provider (`StreamingService`): issues the signed
  URLs above.
- `streaming` feature plugin: authenticated `GET /api/stream-token/{id}`
  / `GET /api/download-token/{id}`.
- The raw `/stream/{media_id}` HTTP handler (registered directly by
  `server.py`, next to `/healthz` - `ApiRouter` is JSON-only): verifies
  the signed URL, then serves bytes from `StorageProvider` with `Range`
  support (206/416), `Content-Disposition: attachment` for downloads.
  This one endpoint is both "Streaming" and "Download"/"Offline
  Download" - see `docs/architecture/streaming.md`.
- Mini App core screens (React + Vite + TypeScript + Tailwind, no
  routing/state library beyond React itself): Search, Browse (genre grid
  + per-genre list), Media Details (variant selection), Player (native
  `<video>`, resumes via `continue_watching`, reports progress), shared
  UI components, and an in-memory navigation stack. See `miniapp/README.md`.

**Written, not yet executable-verified** (no `kurigram` install/live
Telegram credentials, and no network to `npm install` the Mini App's
dependencies, in the environment this was built in):
- `storage_telegram` provider (`StorageProvider`): reads file bytes
  directly from Telegram via a dedicated, lazily-connecting kurigram
  client pool, separate from the bot-core `TelegramGateway`. Same
  verification caveat as `telegram_kurigram`.
- The Mini App's dependency-resolution/build step (`npm install` /
  `vite build`) - source syntax-checked with `esbuild` (parse +
  full-bundle resolution against a real, separately-installed React) but
  not run through `tsc`'s type checker or an actual browser, since no
  `@types/react`/`vite`/etc. could be installed offline. Run
  `npm install && npm run typecheck && npm run build` in a
  network-connected environment before deploying.

**Not attempted this pass, and why:**
- Continue Watching / Downloads / Watchlist / Settings / menu *screens*
  in the Mini App - this pass's scope was explicitly "Search page,
  Browse page, Media Details page, Video Player, Navigation state,
  React frontend"; see `miniapp/README.md`'s "Deliberately not built
  this pass" section for what each remaining screen needs (mostly:
  nothing architecturally new, follow the same page pattern, plus new
  backend routes for Watchlist/Settings which don't exist yet either).
- A worker-pool-wide adaptive block-size/prefetch strategy beyond
  kurigram's own chunking, and a server-side stream-token revocation
  list - both noted in `docs/architecture/streaming.md` as later
  refinements, not blockers.
- Broadcast, Statistics, Notifications, Admin Dashboard, Inline Search,
  Channel Access - unchanged from the Phase 3 notes below; still fully
  buildable now with fake/null adapters, just not reached in this pass.

## Future
Additional plugin categories (Anime, Music, Books, Sports, Live
Channels, AI features) as independent plugins, per the plugin
architecture - no core changes required to add them.
