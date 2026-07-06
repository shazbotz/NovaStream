# Telegram Media Platform — Architecture Design (Phase 1, v2)

**Status:** Supersedes `architecture-design-phase1.md`. Still design-only — no implementation started.
**Change driver:** ten mandatory requirements — search/storage/streaming abstraction, feature flags, plugin architecture, dependency rules, AI-readiness, full feature preservation.
**Scope note, carried over unchanged from the prior turn:** "preserve all existing features" below means the legitimate engineering feature set (search, filters, streaming, indexing, metadata, admin, broadcast, stats, genre browsing, Mini App). Shortlink monetization, force-sub growth tactics, and copyright-evasion mechanisms remain out of scope, as agreed.

---

## 0. What changed from v1

Everything in v1 §2 (Koyeb constraints), §4.3's block-prefetch streaming design, §4.5's TTL cache, the signed-URL scheme, and the Mongo-text-index search *implementation* are all still correct and still the Phase 1 defaults. What's new here is the **shape around them**: instead of the catalog/streaming/cache modules being called directly, everything now sits behind explicit interfaces, and features are organized as plugins loaded by a small core kernel instead of being hardwired into the bot. v1 was "a clean modular monolith." v2 is "a plugin kernel with swappable adapters" — a stricter version of the same instance-count and language constraints.

---

## 1. Architectural style

**Ports & Adapters (hexagonal) for the technical seams, a plugin kernel for the feature seams.** Two different problems, two matching patterns:

- *"Swap MongoDB for Meilisearch/S3/a Go streaming service without touching application code"* → this is a ports & adapters problem. Define the interface (port), write one adapter per backend, inject the chosen adapter at startup.
- *"Add a Music or Anime module next year without editing core files"* → this is a plugin problem. Define a plugin contract, let each feature register itself into the core through that contract, load plugins by discovery instead of by import list.

Using the same tool for both would be worse at each — a single interface can't sanely represent "which Telegram-vs-search-vs-storage backend" *and* "which of fifteen optional features are active." Keeping them separate keeps each simple.

### Dependency direction (requirement 8: clean dependency rules)

```
plugins/  ──depends on──►  services/  ──depends on──►  domain/ (interfaces + models)
                                                              ▲
adapters/ (mongo, telegram, s3, meilisearch, ...) ───implements┘
composition_root (server.py)  ──wires adapters into services at startup, once
```

Rules, enforced by directory structure and import-linting (not just convention):
- `domain/` imports nothing from this project except itself. No Mongo, no Pyrogram, no aiohttp.
- `adapters/*` may import `domain/` and their own external library. Adapters never import each other.
- `services/` imports only `domain/` interfaces — never a concrete adapter class by name.
- `plugins/*` import only `services/` (through `PluginContext`, see §3) — never `adapters/` directly, never another plugin's module directly. Cross-plugin needs go through a `services/` facade.
- `server.py` (composition root) is the **only** file allowed to import both an interface and its concrete adapter and wire them together.

This is what actually prevents circular imports and hidden dependencies — it's not a style guideline, it's a constraint the layout makes structurally hard to violate. It also retires the `temp` / `BUTTONS` / `FILTER_STATE` global-mutable-state pattern for good: state a plugin needs is either request-scoped, passed through `PluginContext`, or lives behind a service — never a bare module-level dict.

---

## 2. Core interfaces (ports)

### 2.1 SearchEngine (requirement 1)

```python
class SearchEngine(Protocol):
    async def index(self, doc: SearchDocument) -> None: ...
    async def remove(self, doc_id: str) -> None: ...
    async def search(self, query: SearchQuery) -> SearchResult: ...
    async def suggest(self, prefix: str, limit: int = 10) -> list[str]: ...
```

`SearchQuery` and `SearchResult` are plain domain dataclasses (query text, filters, offset/limit, ranking hints in; scored hits, next-offset, total out) — no Mongo cursor, no engine-specific object ever crosses this boundary.

`CatalogService` (in `services/`) is the *only* thing that calls `SearchEngine`. Nothing else in the codebase — no plugin, no handler — imports a search adapter directly.

**Phase 1 adapter:** `MongoTextSearchEngine`, using the native `$text` index from v1 §4.2. **Future adapters, same interface, zero application changes:** `AtlasSearchEngine`, `MeilisearchEngine`, `TypesenseEngine`, `ElasticsearchEngine`, `PostgresFTSEngine`. The `suggest()` method exists from day one even though the Phase-1 Mongo adapter implements it naively (prefix query) — this is the seam where autocomplete, fuzzy matching, typo tolerance, synonyms, and phonetic matching land later, in a new adapter, without a `CatalogService` change. Multilingual search and ranking tuning are adapter concerns (e.g., Meilisearch's built-in typo tolerance and per-language tokenizers) — the interface doesn't need to know how a given engine achieves them.

### 2.2 StorageProvider (requirement 2)

```python
class StorageProvider(Protocol):
    async def put(self, key: str, source: AsyncIterator[bytes]) -> StorageRef: ...
    async def get_range(self, ref: StorageRef, start: int, end: int) -> AsyncIterator[bytes]: ...
    async def get_metadata(self, ref: StorageRef) -> FileMetadata: ...
    async def delete(self, ref: StorageRef) -> None: ...
```

`StorageRef` is an opaque, provider-tagged value stored on the catalog record instead of a bare Telegram `file_id`:
```python
{"provider": "telegram", "chat_id": -100..., "message_id": 12345}
{"provider": "s3",       "bucket": "media", "key": "movies/abc.mkv"}
{"provider": "r2",       "bucket": "...", "key": "..."}
```
The catalog doesn't care which shape it holds. **Phase 1 adapter:** `TelegramStorageProvider` — this is where v1's worker-pool + block-prefetch design (v1 §4.3) actually lives now: `get_range()` *is* the concurrent block-prefetch implementation, just reached through this interface instead of called directly. **Future adapters, same interface:** `S3StorageProvider`, `R2StorageProvider`, `B2StorageProvider`, `GDriveStorageProvider`, `LocalStorageProvider` — useful for e.g. moving a hot/popular title to R2 to take load off the Telegram-sourced path, or letting an operator upload original content directly instead of forwarding it through a Telegram channel first. Storage backend is chosen per-item (via `StorageRef.provider`), not globally — a catalog can mix items from multiple providers from day one.

### 2.3 StreamingService (requirement 3: complete streaming isolation)

```python
class StreamingService(Protocol):
    async def get_playback_url(
        self, media_id: str, user_id: int, *, expiry_seconds: int = 21600
    ) -> PlaybackURL: ...
    async def revoke(self, media_id: str, user_id: int) -> None: ...
```

This is the entire surface the bot is allowed to know about. The bot calls `get_playback_url()`, gets back a `PlaybackURL` (a plain string + expiry), and puts it on a button. It never sees a `StorageRef`, a worker pool, a block size, or a Telegram client. Internally, `StreamingService`:
1. Looks up the catalog item's `StorageRef`.
2. Resolves the right `StorageProvider` adapter for that ref.
3. Issues the HMAC-signed, expiring URL (v1 §4.3).
4. The actual HTTP range route (`/stream/{id}`) validates the signature, then calls `StorageProvider.get_range()` to serve bytes — it does **not** live in the bot process's request path conceptually, even though it's deployed in the same container for Phase 1.

Because the interface is defined purely in terms of plain data in and plain data out (a media id and a user id in, a URL string out — no shared connections, no in-process objects crossing the boundary), swapping the in-process implementation for an HTTP call to a standalone streaming service (Python, Go, Rust — doesn't matter) later is a **pure adapter swap**, exactly like §2.1 and §2.2:
```python
# Phase 1: in-process
streaming = LocalStreamingService(storage=storage_registry, tokens=token_signer)

# Later: separate service, no code changes anywhere else
streaming = RemoteStreamingService(base_url=config.STREAMING_SERVICE_URL)
```
Both satisfy the same `StreamingService` Protocol, so `CatalogService`, every plugin, and the bot handlers that request playback URLs don't change at all when this flips.

### 2.4 TelegramGateway (requirement 7: Cache → DB → Telegram API)

```python
class TelegramGateway:
    async def get_chat_member(self, chat_id: int, user_id: int) -> MemberStatus: ...
    async def get_messages(self, chat_id: int, ids: list[int]) -> list[Message]: ...
    async def send_message(self, chat_id: int, text: str, **kw) -> Message: ...
    async def forward_message(self, ...): ...
```
Every plugin and every service talks to Telegram **exclusively** through this gateway — there is no other way to reach a Pyrogram/kurigram client in the codebase (the composition root holds the real client; nothing else gets a reference to it). Internally, every method follows the same fixed order:

```
1. Check bounded TTL cache  →  hit? return.
2. Check database            →  hit and fresh? return, warm the cache.
3. Call Telegram              →  store in DB + cache, return.
```

This is what structurally fixes v1's `is_subscribed()` finding (one API call per channel per message) — it's no longer possible for a plugin to accidentally bypass the cache, because there's no direct client access to bypass it *with*. FloodWait handling, exponential backoff, and outbound rate limiting live once, inside this gateway, instead of being duplicated per call site across the codebase.

### 2.5 FeatureFlags (requirement 4)

```python
class FeatureFlags(Protocol):
    async def is_enabled(
        self, feature: str, *, user_id: int | None = None,
        chat_id: int | None = None, group_id: int | None = None,
    ) -> bool: ...
    async def set(self, feature: str, enabled: bool, *, scope: FlagScope) -> None: ...
```
Resolution order, most specific wins: **env kill-switch → user override → chat/group override → global default.** The env kill-switch exists so an operator can force a feature off platform-wide (e.g., during an incident) regardless of what's stored in the database. Backed by a small collection, read through the same bounded TTL cache module from v1 §4.5 — checking a flag in the hot path is a memory lookup, not a database round trip.

---

## 3. Plugin system (requirement 5)

### 3.1 Plugin contract

```python
class Plugin(Protocol):
    name: str
    version: str
    requires: tuple[str, ...] = ()   # other plugin names that must load first

    def register(self, ctx: PluginContext) -> None:
        """Called once at startup. Register everything the plugin owns."""
```

### 3.2 PluginContext — the only thing a plugin is handed

```python
@dataclass
class PluginContext:
    commands: CommandRegistry      # plugin.commands.register("movies", handler)
    callbacks: CallbackRegistry    # plugin.callbacks.register("mv_", handler)  — prefix-routed, see v1 §4.1
    api: APIRouter                 # plugin.api.get("/movies/{id}", handler)
    scheduler: JobScheduler        # plugin.scheduler.every("1h", cleanup_job)
    settings: SettingsRegistry     # plugin.settings.register("movies.page_size", default=10)
    models: ModelRegistry          # plugin.models.register(MovieWatchStats, collection="movies_watch_stats")
    services: ServiceLocator       # read-only: .catalog, .streaming, .storage, .telegram, .flags, .cache
```
A plugin never imports `aiohttp`, `pyrogram`, or `motor` directly to do its job — everything it needs is reachable through `ctx`. This is what makes "core doesn't need modification when a plugin is added" actually true: the core kernel only knows about `CommandRegistry`/`CallbackRegistry`/`APIRouter`/`JobScheduler`, never about "the Movies plugin" specifically.

### 3.3 PluginManager — discovery and load order

- Plugins live one-per-directory under `plugins/`, each exposing a `Plugin` instance.
- At startup, the manager discovers all plugin directories, topologically sorts them by `requires`, and calls `register(ctx)` on each in order. A plugin with unmet `requires` fails loudly at startup (not silently at first use).
- **Load-time gating vs runtime gating** (this is the answer to requirement 4's "global enable/disable... environment-based configuration" *and* "per-chat/per-group/per-user" both being required):
  - A plugin disabled via `PLUGINS_DISABLED=ai-features,live-channels` env var is **never imported** — zero RAM, zero startup cost. This is for heavy/optional plugins on the 512MB budget.
  - A plugin that's loaded but should be toggle-able per chat/group/user at runtime (e.g., inline-search off in one group) checks `FeatureFlags.is_enabled()` at the top of its handler — a cached lookup, effectively free, but the code stays loaded.
- Core itself (bot bootstrap, `TelegramGateway`, `FeatureFlags`, `PluginManager`, `/healthz`) is not a plugin and is always loaded — everything else is.

### 3.4 Core vs. plugin responsibilities

| Core (kernel, always on) | Plugins (optional, independently toggleable) |
|---|---|
| Telegram client lifecycle, `TelegramGateway` | Catalog & Search (Auto-Filter equivalent) |
| `FeatureFlags`, bounded TTL cache module | IMDb/metadata enrichment |
| `PluginManager`, command/callback/route/job registries | Streaming, Download, External Player |
| `/healthz`, structured logging, graceful shutdown | Telegram Mini App (API + static hosting pointer) |
| Composition root (adapter wiring) | Genre Browsing, Recommendations, Continue Watching |
| | Inline Search, Broadcast, Statistics, Notifications |
| | Admin Dashboard |
| | Channel-gated access (generic membership gating, config-driven — not growth mechanics) |
| | *(future)* Anime, Music, Books, Sports, Live Channels, AI Features |

---

## 4. Application services layer (requirement 9: AI-readiness)

Plugins don't touch `SearchEngine`/`StorageProvider`/`TelegramGateway` adapters directly — they go through a thin **services** facade that composes them into task-shaped operations:

```python
class CatalogService:
    async def search(self, query: SearchQuery) -> SearchResult: ...
    async def get_item(self, media_id: str) -> CatalogItem: ...
    async def index_item(self, ...): ...

class PlaybackService:
    async def request_playback(self, media_id: str, user_id: int) -> PlaybackURL: ...

class HistoryService:
    async def record_progress(self, user_id: int, media_id: str, position: int) -> None: ...
    async def continue_watching(self, user_id: int) -> list[CatalogItem]: ...
```

This is the layer a future AI plugin (semantic search, recommendations, an LLM-based chat interface over the catalog) is built on: it composes `CatalogService`, `HistoryService`, and `PlaybackService` the exact same way an "Anime" or "Music" plugin would, through the exact same `PluginContext.services`. There's no separate "AI integration point" to design — a recommendation engine is just another plugin that reads `HistoryService` and `CatalogService` and writes to a `recommendations` collection it registers itself. Nothing in core needs to know AI plugins exist as a category.

---

## 5. Performance implications of this design (requirement 6)

Interfaces and plugins are a maintainability tool, not an excuse to add overhead on a 512MB/0.1vCPU box. Concretely:

- Interface dispatch is a Python `Protocol` — no runtime cost beyond a normal method call; there's no reflection or dynamic proxying happening per request.
- Plugin `register()` runs once at startup, not per request — the cost is a one-time, small addition to cold-start time, not a steady-state cost.
- Env-disabled plugins are never imported, so they cost nothing — RAM, startup time, or otherwise.
- Feature-flag checks in the hot path are bounded-TTL-cache reads (in-process dict lookup), not database round trips.
- `TelegramGateway`'s cache-first policy means the *steady-state* cost of "is this user a member of channel X" is a cache hit, not an API call, directly serving requirement 7.
- Adapters are chosen once at startup by the composition root and held as singletons — no per-request construction of a Mongo client, search client, or storage client.

---

## 6. Revised repository layout

```
media-platform/
  domain/
    models.py            # SearchQuery, SearchResult, StorageRef, PlaybackURL, MemberStatus, ...
    interfaces.py         # SearchEngine, StorageProvider, StreamingService Protocols
  adapters/
    search/
      mongo_text.py       # Phase 1 default
      meilisearch.py       # future
    storage/
      telegram.py          # Phase 1 default — worker pool + block prefetch lives here
      s3.py                 # future
      r2.py                 # future
    telegram_gateway.py    # cache-first Telegram access, retry/FloodWait/rate-limit
  services/
    catalog_service.py
    playback_service.py
    history_service.py
    feature_flags.py
  cache/
    ttl_cache.py
  kernel/
    plugin.py              # Plugin Protocol, PluginContext
    plugin_manager.py       # discovery, load order, registries
    command_registry.py
    callback_registry.py     # prefix-routed dispatch, v1 §4.1
    api_router.py
    scheduler.py
  plugins/
    catalog_search/
    metadata_imdb/
    streaming/
    download/
    mini_app/
    genre_browsing/
    continue_watching/
    inline_search/
    broadcast/
    statistics/
    notifications/
    admin_dashboard/
    channel_access/
  server.py                 # composition root: reads config, builds adapters, boots kernel + plugins
  config.py
  miniapp/                   # separate frontend project, unchanged from v1
  tests/
  Dockerfile
```

---

## 7. Data model additions

```
feature_flags
  _id: feature_name
  global_default: bool
  overrides: [{scope: "chat"|"group"|"user", id: int, enabled: bool}]

storage_refs   # embedded on catalog items, not a separate collection:
  media._storage: {provider: str, ...provider-specific fields}
```
Everything else from v1 §5 (`media`, `users`, `watch_progress`, `channels`) is unchanged — the plugin/interface layer sits on top of the same data model, it doesn't replace it.

---

## 8. Feature inventory → plugin mapping

| Reference-repo capability | New home | Notes |
|---|---|---|
| Auto Filter / Manual Filter | `plugins/catalog_search` | via `SearchEngine` interface |
| IMDb metadata | `plugins/metadata_imdb` | generic enrichment, cached |
| Stream / Download buttons | `plugins/streaming`, `plugins/download` | via `StreamingService`, same message as file (v1 requirement, unchanged) |
| Genre browsing | `plugins/genre_browsing` | builds on `CatalogService` |
| Broadcast | `plugins/broadcast` | keeps v1's semaphore-bounded fan-out design |
| Statistics | `plugins/statistics` | |
| Admin panel | `plugins/admin_dashboard` | in-Telegram UI kept, backed by `settings` registry from every other plugin |
| Force-Subscribe | `plugins/channel_access` | reframed as generic, config-driven membership gating; no growth-hacking logic; **excluded from Phase 1 unless you confirm a legitimate use case for it** |
| File Protection / auto-delete | *not implemented as a plugin in Phase 1* | Telegram's native `protect_content` flag and scheduled-deletion are generic platform capabilities, not something this design builds a subsystem around; revisit only for a concrete legitimate need (e.g. ephemeral sensitive content) |
| Shortlink monetization | **excluded**, per prior agreement | |
| Request System | `plugins/catalog_search` (extension) | user requests missing titles — generic feature, no distribution-specific logic |
| Inline search | `plugins/inline_search` | |

---

## 9. Updated open decisions

Same six from v1 §10, plus:
7. **Plugin scope for Phase 2:** start with the minimal set (`catalog_search`, `streaming`, `download`, `mini_app`) and add the rest incrementally, or scaffold all listed plugins as empty stubs now so the registries/settings surface is complete from day one?
8. **`channel_access` plugin:** build it now (generic, config-driven) or leave it out until you have a concrete legitimate access-gating need?

Phase 2 implementation order, updated for this design: `domain/` + `kernel/` (the two things everything else depends on) → `adapters/telegram_gateway.py` + `adapters/search/mongo_text.py` + `adapters/storage/telegram.py` (Phase 1 defaults) → `services/` → `plugins/catalog_search` → `plugins/streaming` → `plugins/mini_app` → remaining plugins.
