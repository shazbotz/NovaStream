# Telegram Media Platform — Architecture Design (Phase 1)

**Status:** Draft for review. No implementation has started — per the brief, this is the design to approve before any code is written.
**Scope:** Engineering architecture only — search/indexing, database design, streaming, caching, Mini App, security, scalability. Piracy-adjacent workflows (shortlink monetization, force-sub growth tactics, copyright-evasion mechanisms) from the reference repos are intentionally excluded, as agreed.

---

## 1. What we learned from the four reference repos

### Master-2 (kurigram AutoFilter bot) — the most complete reference
**Worth keeping, conceptually:**
- The producer/consumer indexing pipeline (`plugins/index.py`): bounded-concurrency `asyncio.Queue` workers fetching message batches, a separate bounded pool saving to the DB, per-chunk error isolation, FloodWait-safe retries. This is genuinely good design.
- The broadcast system (`plugins/broadcast.py`): semaphore-bounded fan-out, chunked batches, progress updates, automatic retry pass for failures. Also good.
- The in-Telegram admin panel (`plugins/admin.py`): a full nested-menu settings UI operable entirely through inline keyboards. Good UX idea, worth carrying into a proper admin surface.
- Genre-based browsing (`plugins/genre_browse.py` + `genre_cache_db.py`): the closest existing thing to poster-based catalog browsing — a real precursor to the Mini App.
- HTTP range handling in `plugins/webcode.py` is spec-correct (proper 206 responses, suffix-ranges, HEAD support).

**Root causes of its problems:**
- `FILTER_STATE`, `BUTTONS`, `JOIN_REQUEST_USERS`, `SPELL_CHECK` are unbounded module-level dicts. They never expire and never get cleaned up. This is *why* `bot.py` restarts the entire process every 24h via `os.execl` — that's a patch for a memory leak, not a fix.
- Search (`database/ia_filterdb.py`) matches filenames with a Python-side/Mongo regex built as `re.escape(term)` joined by `.*` — an **infix regex scan**. Regex like this cannot use a B-tree/text index; every search is a full collection scan. It works at small scale because of a 30-second, 256-entry LRU cache in front of it, but that cache is invalidated on every write and is per-process (doesn't help a second replica).
- "Multi-Mongo sharding" (`DATABASE_URI2..5`) is scatter-gather: writes hash to one shard, but *every read fans out to all shards* and merges in application code. That's not sharding for read performance — it's only a workaround for MongoDB Atlas's free-tier 512MB-per-cluster cap.
- `is_subscribed()` (`utils.py`) makes one `client.get_chat_member()` Telegram API call *per configured channel, per message*, sequentially, with no cache. On every qualifying message. This directly fights the brief's "minimal Telegram API calls" goal.
- Streaming (`streaming/stream_dl.py`) goes through a single Pyrogram client's `stream_media()` — one MTProto connection handling every concurrent viewer. No worker pool, no parallel chunk fetching.
- `plugins/pm_filter.py`'s `cb_handler` is a ~540-line function dispatching on `elif query.data.startswith(...)` chains — O(n) dispatch, and a genuine maintainability hazard at that size.
- `requirements.txt` has 50+ packages, including things unrelated to this bot's job (OpenCV, NumPy, OpenAI SDK, yt-dlp/youtube-dl, two different web frameworks). This directly hurts image size, cold-start time, and RAM headroom — all three are scored resources on a 512MB instance.
- Config defaults in `info.py` hardcode real-looking channel/admin/group IDs as fallback values instead of failing fast when required env vars are missing.

### Inline-Filter-Bot — small, but two lessons
- **Good idea:** true Telegram inline-mode search (`@bot query` from any chat) as a second search entry point, independent of group membership.
- **Anti-patterns to avoid:** synchronous `pymongo.MongoClient` calls made from inside `async def` functions — this blocks the entire event loop on every DB call. And `eval(button)` deserializing stored button layouts — arbitrary code execution risk from data that's meant to be inert. Both are fixed trivially (motor for async Mongo I/O, `json.loads` instead of `eval`).

### TG-FileStreamBot (Go) — the strongest streaming reference
This is a single-purpose streaming proxy (no search/filter/database at all), and that focus shows in the quality of the streaming path specifically:
- **Multi-bot-token worker pool** (`internal/bot/workers.go`): N bot clients started concurrently, requests round-robin across them (`GetNextWorker()`). This is the direct fix for Master-2's single-connection bottleneck — it distributes MTProto load (and Telegram's per-connection rate limits) across multiple accounts.
- **Concurrent block-prefetch streaming pipe** (`internal/stream/pipe.go`): instead of fetching one sequential chunk at a time, it fetches a *batch* of blocks in parallel (`StreamConcurrency`, default 4), with adaptive block sizing (64KB for small seeks up to 1MB for large sequential reads), retried with exponential backoff, ordered back into a channel for the HTTP writer. This is the single biggest streaming-throughput idea across all four repos and directly targets "instant playback" and "fast seeking."
- **Bounded in-memory metadata cache** (`internal/cache/cache.go`, `freecache`, fixed 10MB) to avoid re-fetching message metadata from Telegram on every request — a concrete instance of "minimal Telegram API calls."
- **Centralized flood-control middleware** at the client layer, instead of scattered `try/except FloodWait` calls.
- Auth is a deterministic hash of file properties (name+size+mime+id), truncated — better than Master-2's 6-char `file_unique_id` prefix (harder to guess), but still **not time-limited**: once issued, a link works forever with no revocation. Worth improving, not copying as-is.

### EvaMaria
The repository is archived; `bot.py` only prints `EOL: exiting..` and the source has been removed. `requirements.txt` shows it used `motor`/`pymongo` with `marshmallow`/`umongo` (a schema-validating ODM) — notably, none of the other three repos validate document shape at all, which is worth reinstating. Beyond that, there's nothing left to audit.

### Cross-cutting patterns worth carrying forward
1. Producer/consumer pipelines with bounded concurrency for anything bulk (indexing, broadcast).
2. Range-request HTTP handling done correctly (all repos got the byte-range mechanics right).
3. In-Telegram admin UX as a fast operational surface, in addition to (not instead of) a real admin API.
4. "Stream" and "Download" as buttons on the same message as the file — never a separate message.

### Cross-cutting problems to design out
1. Unbounded in-process global state used as a substitute for a real cache/session store.
2. Search implemented as unindexed regex/LIKE scans.
3. Single-connection streaming with no horizontal fan-out.
4. Permanent, unsigned, non-expiring media links.
5. Defensive `try/except` scattered per-call instead of centralized retry/backoff policy.
6. Dependency and feature sprawl inherited from repeated forking.

---

## 2. Constraints that shape every decision below

You said the deployment target is Koyeb's free tier. Current specifics, since they materially change the design:

| Constraint | Value | Design implication |
|---|---|---|
| RAM | 512MB | Every long-lived cache must be bounded; avoid heavy frameworks/deps |
| CPU | 0.1 vCPU | Avoid CPU-bound work on the request path (no in-process video transcoding) |
| Instances | **1 free instance per org** | Can't run separate services and get the free tier for each — components must co-exist in one deployable unit, or extra services must live elsewhere (see §9) |
| Regions | Frankfurt or Washington D.C. only | No multi-region on free tier |
| Scale-to-zero | After 1h idle | Cold start time matters; slim image, lazy-load heavy modules |
| Shutdown | SIGTERM, 30s grace, then SIGKILL | The app must handle SIGTERM: stop accepting new streams, let in-flight ones finish within ~30s |
| Persistent volumes | Not available on free tier | No local disk state — sessions/cache must be either external or ephemeral-and-rebuildable |

This is why the design below is a **modular monolith with clean internal boundaries**, not a microservices deployment — the free tier physically can't host separate services with their own free allocation. The module boundaries are drawn so that any one piece (streaming, search, API) can be lifted into its own service later with no rewrite, once/if you move off the free tier.

---

## 3. System overview

```
                       ┌─────────────────────────────┐
                       │   Telegram (Bot API/MTProto) │
                       └───────────────┬─────────────┘
                                        │
                        ┌───────────────┴───────────────┐
                        │      Single Koyeb instance      │
                        │  ┌───────────────────────────┐ │
Mini App (static, ─────►│  │  aiohttp HTTP surface     │ │
hosted on a CDN,        │  │  - JSON API (/api/*)      │ │
NOT on this instance)   │  │  - Streaming (/watch,/dl) │ │
                        │  │  - Health (/healthz)      │ │
                        │  └─────────────┬─────────────┘ │
                        │                │                │
                        │  ┌─────────────┴─────────────┐ │
                        │  │  Bot Core (handlers)       │ │
                        │  └─────────────┬─────────────┘ │
                        │  ┌─────────────┴─────────────┐ │
                        │  │  Catalog / Search engine   │ │
                        │  ├────────────────────────────┤ │
                        │  │  Streaming engine          │ │
                        │  │  (worker pool + prefetch)  │ │
                        │  ├────────────────────────────┤ │
                        │  │  Bounded TTL cache module  │ │
                        │  └────────────────────────────┘ │
                        └───────────────┬────────────────┘
                                        │
                         ┌──────────────┴──────────────┐
                         │   MongoDB (Atlas free tier)  │
                         └──────────────────────────────┘
```

Everything inside the instance is **one process, one port** — required by the single-free-instance constraint — but organized as isolated modules communicating through interfaces, not global state.

---

## 4. Component design

### 4.1 Bot Core
Thin layer: registers handlers, delegates to the catalog/search and streaming modules, renders responses. No business logic lives in handler functions.

**Fix for the 540-line `cb_handler`:** replace the `elif data.startswith(...)` chain with a routing table —

```python
CALLBACK_ROUTES: dict[str, Handler] = {
    "flt_": filter_open,
    "fpk_": filter_pick,
    "next": next_page,
    "close_data": close_message,
    # ...
}

async def dispatch(client, query: CallbackQuery):
    prefix = next((p for p in CALLBACK_ROUTES if query.data.startswith(p)), None)
    handler = CALLBACK_ROUTES.get(prefix)
    if handler:
        await handler(client, query)
```

O(1)-ish dispatch (small fixed table), each handler in its own file, independently testable.

**Fix for `is_subscribed()`:** membership checks go through the bounded TTL cache (§4.5) keyed by `(user_id, channel_id)`, TTL a few minutes. One Telegram API call per user per channel per TTL window, not per message.

### 4.2 Catalog & Search Engine
Repository-interface pattern instead of `if USE_MONGO: ... else: ...` branching inside every function (the pattern in `ia_filterdb.py`/`users_chats_db.py` today):

```python
class MediaRepository(Protocol):
    async def save(self, media: MediaRecord) -> SaveResult: ...
    async def search(self, query: SearchQuery) -> SearchResult: ...
    async def get(self, media_id: str) -> MediaRecord | None: ...

class MongoMediaRepository(MediaRepository): ...
class PostgresMediaRepository(MediaRepository): ...  # optional, see §10
```

**Search fix — the highest-leverage change in this whole design:** replace infix regex with a MongoDB **text index** (`db.media.create_index([("file_name", "text"), ("caption", "text")])`). Text indexes are tokenized, stemmed, and usable by the query planner — turning a full collection scan into an actual index lookup. This is a native, free-tier-compatible Mongo feature, not an add-on service. Filters (language/quality/season/episode) become indexed equality/range fields alongside the text search, not post-hoc regex on filenames.

*Optional upgrade path once catalog size or query volume justifies it:* a dedicated search engine (MongoDB Atlas Search, or a self-hosted Meilisearch/Typesense instance) for fuzzy/typo-tolerant ranked search. Not recommended for Phase 1 — it's another service to run, and the free-tier RAM budget doesn't comfortably fit it alongside everything else. Verify current free-tier terms for whichever you pick when you get there.

Document schema gets actual validation (via Pydantic models at the application boundary) — closing the gap all three living repos share of writing untyped dicts straight to the DB.

### 4.3 Streaming Engine
This is the component with the most room for improvement, and where TG-FileStreamBot's design translates most directly.

**Design (Python/asyncio, no second language required for Phase 1):**
- **Worker pool:** if you have more than one bot token available, start N Pyrogram/kurigram clients at boot, round-robin requests across them — mirrors `GetNextWorker()`. With a single token, the engine still works, just without the extra fan-out; this is a config knob (`STREAM_WORKER_TOKENS=token1,token2,...`), not an architectural fork.
- **Concurrent block prefetch:** instead of one sequential `stream_media()` generator, issue a small batch of parallel low-level `upload.GetFile` calls (via `asyncio.gather` under a bounded semaphore) and feed an ordered `asyncio.Queue` that the HTTP response reads from. Adaptive block size (64KB–1MB depending on requested range size), matching TG-FileStreamBot's approach.
- **Retry policy:** exponential backoff per block, capped attempts, single place FloodWait is handled (not duplicated per call site).
- **No full-file buffering, ever** — constant memory per stream regardless of file size, same principle Master-2 already gets right, kept.

**Signed, expiring stream URLs — new, and the main security fix:**
```
token = HMAC-SHA256(secret, f"{file_id}:{user_id}:{expiry_ts}")
url   = /stream/{file_id}?exp={expiry_ts}&sig={token}&u={user_id}
```
Short TTL (config, e.g. 6–24h), reissued on demand by the bot/Mini App. This replaces both Master-2's guessable 6-char prefix and TG-FileStreamBot's permanent unsigned hash — links stop working after expiry instead of working forever once leaked.

**Rate limiting:** a token-bucket limiter per IP and per user on the streaming route — none of the four repos have this, and an open streaming endpoint is a bandwidth-abuse target.

### 4.4 Mini App
- **Frontend:** React + Vite + Tailwind, built as a static bundle and hosted on a CDN/static host (Cloudflare Pages, Vercel, GitHub Pages — pick based on what you already use) — **not served from the 512MB instance.** That instance should spend its RAM/CPU on the bot and streaming, not static asset delivery.
- **Auth:** validate Telegram's `initData` (HMAC-SHA256 signed by your bot token, per Telegram's documented WebApp scheme) on every Mini App API call. This authenticates the calling Telegram user without a separate login system.
- **API surface** (JSON, served from the same aiohttp app as the streaming routes): `/api/search`, `/api/media/{id}`, `/api/genres`, `/api/continue-watching`, `/api/stream-token/{id}` (issues the signed URL above).
- **Player:** keep Vidstack (already in the reference templates and a reasonable modern choice) — HLS support, PiP, playback speed, subtitle tracks, full-screen out of the box.
- **New capability none of the four repos have:** watch-progress persistence. A small `watch_progress` collection keyed by `(user_id, media_id)`, updated by periodic `POST` from the player (e.g., every 15–30s or on pause), read on catalog load to power "Continue Watching."

### 4.5 Bounded TTL Cache Module
One reusable utility, used everywhere the old code used an unbounded global dict:
```python
class TTLCache(Generic[K, V]):
    def __init__(self, max_size: int, ttl_seconds: float): ...
    def get(self, key: K) -> V | None: ...
    def set(self, key: K, value: V) -> None: ...
```
Used for: search-result cache, membership-check cache, pagination/filter session state (replaces `FILTER_STATE`/`BUTTONS`), file-metadata cache (replaces re-fetching messages from Telegram).

This is what actually fixes the daily `os.execl` restart — the restart was working around unbounded growth, not fixing it. With every cache bounded, there's no growth to work around, and the process can run indefinitely (or restart on deploy, not on a timer).

*Scale-up note:* these caches are in-process, so on a single instance they're globally consistent by definition. If you ever run more than one instance, in-process caches diverge across replicas — at that point, move this module's backing store to Redis (Upstash's free tier is a reasonable fit for serverless/low-traffic use — confirm current limits when you get there) without changing the module's interface.

---

## 5. Data model (illustrative, MongoDB)

```
media
  _id: file_unique_hash
  file_id, file_ref, file_name, normalized_name
  file_size, file_type, mime_type
  caption
  language, quality, season, episode   # parsed once at index time, not per search
  created_at
  indexes: text(file_name, caption), (language,1), (quality,1), (season,1,episode,1)

users
  _id (telegram user id), name, ban_status, settings

watch_progress
  _id: f"{user_id}:{media_id}"
  user_id, media_id, position_seconds, duration_seconds, updated_at
  index: (user_id, updated_at desc)   # powers "Continue Watching"

channels (indexing sources, admin-managed)
  _id, title, last_indexed_message_id
```

Parsing language/quality/season/episode **once at index time** (extending the existing regex helpers found in `pm_filter.py`/`new_updates.py`) rather than on every search request removes repeated regex work from the hot path.

---

## 6. Security summary

| Issue found | Fix |
|---|---|
| Unsigned, non-expiring stream links | HMAC-signed URLs with expiry (§4.3) |
| `eval()` on stored button data (Inline-Filter-Bot) | `json.loads`/typed models |
| Hardcoded fallback admin/channel IDs in config | Required env vars fail fast at startup; no silent defaults |
| Wide-open CORS (`*`) | Restrict to the Mini App's actual origin in production |
| No rate limiting on streaming endpoint | Token-bucket limiter per IP/user |
| No `initData` validation mentioned anywhere | Validate on every Mini App API request |
| Blocking sync DB calls inside async handlers (Inline-Filter-Bot) | Async driver only (motor), enforced by the repository interface |

---

## 7. Reliability & operations

- **Graceful shutdown:** handle `SIGTERM` — stop accepting new stream requests, let in-flight ones drain within Koyeb's ~30s grace window, then exit. Replaces relying on a hard kill.
- **No timer-based restarts.** Root-caused via bounded caches (§4.5) instead.
- **Centralized FloodWait/retry policy** in one place (client wrapper), not duplicated per call site.
- **`/healthz`** endpoint reporting DB connectivity, active stream count, uptime — for the platform's health checks and your own monitoring.
- **Structured logging** kept from the existing `logging.conf` approach, extended with request IDs on the streaming path for traceability.

---

## 8. Repository layout (proposed)

```
media-platform/
  app/
    bot/
      client.py
      handlers/            # search.py, admin.py, catalog.py, settings.py
      middleware/          # flood_control.py, membership_cache.py
      dispatch.py          # callback routing table
    catalog/
      models.py            # Pydantic schemas
      repository.py        # MediaRepository Protocol
      mongo_repository.py
      indexer.py           # producer/consumer ingestion pipeline (kept from Master-2's design)
      search.py
    streaming/
      engine.py            # worker pool + block prefetch
      tokens.py            # signed URL issue/verify
      routes.py
    api/
      routes.py            # Mini App JSON API
      auth.py               # initData validation
      schemas.py
    cache/
      ttl_cache.py
    config.py               # validated settings, fail-fast on missing required vars
    server.py               # aiohttp app factory
  miniapp/                  # separate frontend project
    src/{pages,components,player,api-client.ts}
  tests/
  Dockerfile                # slim base image, multi-stage, pruned deps
  pyproject.toml
```

Every file above has one job. Nothing in this layout resembles the 1,300-line `pm_filter.py` or the 770-line `commands.py`.

---

## 9. Scale-up path beyond the free tier

Because the modules are cleanly separated, moving beyond one free instance is additive, not a rewrite:
1. **Second instance for streaming** — split `streaming/` into its own deployable service once concurrent-stream volume justifies it; the Bot Core talks to it over HTTP instead of an in-process call.
2. **Go streaming engine** — if/when raw streaming throughput becomes the bottleneck (not before — Python asyncio with block-prefetch already gets most of the benefit TG-FileStreamBot demonstrates), the streaming module's interface is narrow enough to reimplement in Go as a sidecar or standalone service without touching the bot or catalog code.
3. **Shared cache** — swap the TTL cache module's backing store for Redis once you run more than one instance.
4. **Dedicated search service** — Atlas Search / Meilisearch / Typesense, once catalog size or ranking quality needs outgrow a Mongo text index.

None of these require redesigning the system — that's the point of drawing the boundaries this way now.

---

## 10. Open decisions I need from you before implementation starts

1. **Database:** stay on MongoDB (matches existing data/ops experience) or move to Postgres (full-text via `tsvector`, stronger relational integrity)? Either fits the repository-interface design.
2. **Streaming worker tokens:** do you have (or can you get) more than one bot token for the streaming worker pool, or should Phase 1 assume a single token?
3. **Hard budget:** is $0/month a hard constraint, or is a small paid add-on (e.g., Redis, a second small instance) acceptable later?
4. **Mini App hosting:** any existing preference/domain for the static frontend (Cloudflare Pages, Vercel, other)?
5. **Existing data:** is there a current Mongo dataset (from Master-2) that needs migrating in, or is this a clean start?
6. **Admin surface:** keep the in-Telegram admin panel as the only admin UI, or also want a small web admin dashboard on the Mini App?

Once these are settled, Phase 2 is implementation, starting with `catalog/` + `bot/dispatch.py` (the foundation everything else sits on), then `streaming/`, then the Mini App.
