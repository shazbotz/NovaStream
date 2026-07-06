# Telegram Media Platform — Architecture Design (Phase 1, v3)

**Status:** Supersedes v2 on the points below; everything else in v2 (plugin kernel, `SearchEngine`/`StorageProvider`/`StreamingService` design, dependency layering, feature flags) stands. Still design-only.

---

## 0. A naming collision worth resolving before it becomes a bug

Your new requirements document reuses "StorageProvider" for something different from what v2 built. Worth being explicit about this rather than silently picking one, since two different things sharing a name is exactly the kind of confusion this whole exercise is trying to design out:

- **v2's `StorageProvider`** = where media **bytes** live (Telegram, S3, R2, B2, Google Drive, Local). Its methods are `put`/`get_range`/`get_metadata`/`delete` on file content.
- **This document's `StorageProvider`** (item 5) lists MongoDB, PostgreSQL, SQLite, MySQL, Redis-backed metadata as implementations — that's the **database/persistence** layer (catalog records, users, watch history, feature flags), a different concern entirely.

Resolution: v2's file-storage interface keeps the name `StorageProvider`. The new one is introduced as **`DatabaseProvider` + `Repository`** (§2 below) — persistence for structured records, not file bytes. If you'd rather rename the file-storage one instead (e.g. to `BlobProvider` or `MediaStorageProvider`), say so and I'll flip it — the important thing is the codebase never has two unrelated things answering to the same interface name.

Also renaming for consistency with your vocabulary: v2's `SearchEngine` → **`SearchProvider`** (same interface, same adapters, name aligned to this document).

---

## 1. New port: `DatabaseProvider` / `Repository`

```python
class Repository(Protocol[T]):
    async def get(self, id: str) -> T | None: ...
    async def save(self, entity: T) -> None: ...
    async def delete(self, id: str) -> None: ...
    async def query(self, filter: QueryFilter) -> list[T]: ...

class DatabaseProvider(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    def repository(self, name: str) -> Repository: ...
```

One `DatabaseProvider` per backend — `MongoDatabaseProvider`, `PostgresDatabaseProvider`, `MySQLDatabaseProvider` — each exposing the same named repositories (`media`, `users`, `watch_progress`, `feature_flags`, `channels`). `services/` asks the provider for a repository by name and never imports a concrete adapter.

**`SQLiteDatabaseProvider`** is included per your list, with a flag on it: SQLite is file-based and effectively single-writer, so it's a fine adapter for local development, tests, or a single-user/offline deployment, but it isn't the one to pick for a concurrent multi-user production deployment. The interface supports it; the recommendation doesn't.

**On "Redis-backed metadata":** Redis is already in this design as the shared-cache upgrade path (v1 §4.5). It's a poor fit as the *primary, queryable* store for a catalog (no native rich querying/indexing the way Mongo/Postgres have) — I'd keep Redis as cache, not system of record, unless you have a specific narrow use case (e.g. ephemeral session state) that genuinely wants a `RedisDatabaseProvider`. Happy to add one if you have that case in mind.

### Why this is a separate port from `SearchProvider`, not the same one
They serve different jobs that real systems deliberately keep apart: `Repository` is the **system of record** (CRUD, source of truth); `SearchProvider` is a **derived, denormalized index** optimized for querying, which may not even be the same database. `CatalogService.index_item()` writes to `MediaRepository` first, then calls `SearchProvider.index()` to update the search index — two writes, one source of truth. This is what makes "move search to Meilisearch, keep Mongo as the record store" possible later without also migrating the catalog's primary storage.

---

## 2. New port: `AuthProvider`

Item 9 (API-first: Bot, Mini App, future Web Dashboard, Desktop, Mobile all use the same backend APIs) implies different clients will eventually authenticate differently, while all producing the same thing services need: *who is this request from*.

```python
class AuthProvider(Protocol):
    async def authenticate(self, credentials: Credentials) -> AuthenticatedPrincipal | None: ...
```

**Phase 1 adapters:** `TelegramInitDataAuthProvider` (validates the Mini App's `initData`, v2 §4.4), `TelegramBotContextAuthProvider` (trivial — a bot update already carries an authenticated Telegram `user_id`). **Future adapters, same interface:** `APIKeyAuthProvider` (server-to-server / a Desktop or Mobile client), `OAuthProvider` (a Web Dashboard with its own login). Every route and service consumes the same `AuthenticatedPrincipal` (user id + roles/scopes) regardless of which adapter produced it.

---

## 3. Generalizing the plugin system to cover providers (item 8)

v2's plugins registered *features* (commands, routes, jobs). Your new list explicitly names **Search Providers, Storage Providers, Authentication Providers, Streaming Providers, Metadata Providers** as plugin categories — meaning adapters themselves should be plugin-discoverable, not hardcoded in the composition root. Extending `PluginContext` with a provider registry:

```python
class ProviderRegistry:
    def register(self, port: str, name: str, factory: Callable[[], Any]) -> None: ...
    def get(self, port: str, name: str) -> Any: ...
```

Built-in adapters ship as **core provider plugins**, registering through the exact same `Plugin.register(ctx)` mechanism as feature plugins:
```python
class MongoSearchProviderPlugin:
    name = "provider.search.mongo_text"
    def register(self, ctx: PluginContext) -> None:
        ctx.providers.register("search", "mongo_text", MongoSearchProvider)
```
The composition root becomes purely config-driven:
```python
search   = providers.get("search",   config.SEARCH_PROVIDER)    # "mongo_text"
storage  = providers.get("storage",  config.STORAGE_PROVIDER)   # "telegram"
database = providers.get("database", config.DATABASE_PROVIDER)  # "mongo"
auth     = providers.get("auth",     config.AUTH_PROVIDER)      # "telegram_init_data"
metadata = providers.get("metadata", config.METADATA_PROVIDER)  # "imdb"
```
A contributor adding Meilisearch support writes one new plugin directory that calls `ctx.providers.register("search", "meilisearch", MeilisearchProvider)` — no core file changes, satisfying "core should automatically discover and load plugins" for adapters, not just features.

**Metadata Providers**, called out explicitly in your list, get the same treatment:
```python
class MetadataProvider(Protocol):
    async def lookup(self, title: str, year: int | None = None) -> MetadataResult | None: ...
```
Phase 1: `IMDbMetadataProvider`. This is also the seam a future Anime plugin uses (`AniListMetadataProvider`) or a future Music plugin uses (`MusicBrainzMetadataProvider`) — each feature plugin can bring its own metadata provider plugin.

### Revised plugin layout
```
plugins/
  providers/                 # implement a port, register via ctx.providers
    search_mongo_text/
    storage_telegram/
    database_mongo/
    auth_telegram_initdata/
    metadata_imdb/
  features/                  # register commands/callbacks/routes/jobs, use ctx.services
    catalog_search/  streaming/  download/  mini_app/
    genre_browsing/  continue_watching/  inline_search/
    broadcast/  statistics/  notifications/  admin_dashboard/  channel_access/
```

---

## 4. API-first rule, made explicit (item 9)

`services/*` is the single implementation of every capability. Bot command handlers and HTTP API route handlers are both required to be **thin**: parse/validate transport-specific input, call exactly one `services/*` method, format transport-specific output. Neither is allowed to contain logic the other can't also reach.

```python
# kernel/command_registry.py handler — bot transport
async def cmd_search(update, ctx: PluginContext):
    result = await ctx.services.catalog.search(SearchQuery.from_text(update.text))
    await update.reply(render_search_results(result))   # bot-specific formatting only

# kernel/api_router.py handler — HTTP transport
async def get_search(request, ctx: PluginContext):
    result = await ctx.services.catalog.search(SearchQuery.from_query_params(request.query))
    return json_response(result)                          # HTTP-specific formatting only
```
Both call the same `CatalogService.search()`. This is what makes the Telegram Bot itself architecturally "just another client" of the platform, on equal footing with the Mini App and any future Web Dashboard/Desktop/Mobile client — not a special case with its own logic path.

---

## 5. Testability (item 12/13), enabled directly by this design

Because every service depends only on Protocols, unit tests inject in-memory fakes instead of hitting real infrastructure:
```python
class InMemorySearchProvider(SearchProvider): ...     # dict-backed, no network
class InMemoryMediaRepository(Repository[CatalogItem]): ...
class FakeTelegramGateway(TelegramGateway): ...        # scripted responses
```
`tests/unit/` runs against fakes — fast, deterministic, no external dependency, runs on every commit. `tests/integration/` runs the real adapters against a disposable Mongo/Postgres and a test bot, on a schedule or pre-release rather than every commit. This split is only possible because nothing in `services/` or `plugins/` imports a concrete adapter directly (§1, v2 §1) — it's a direct payoff of the dependency rule, not a separate effort.

---

## 6. Additional feature-flag entries (item 7)
Added to the flag inventory from v2 §2.5: `subtitles`, `multi_audio`, `analytics`. Same resolution order, same cache-backed lookup — no new mechanism needed, just more names.

---

## 7. Updated repository layout

```
media-platform/
  domain/
    models.py
    interfaces.py           # SearchProvider, StorageProvider, StreamingService,
                             # DatabaseProvider, Repository, AuthProvider, MetadataProvider
  kernel/
    plugin.py  plugin_manager.py  provider_registry.py
    command_registry.py  callback_registry.py  api_router.py  scheduler.py
  services/
    catalog_service.py  playback_service.py  history_service.py  feature_flags.py
  plugins/
    providers/{search_mongo_text, storage_telegram, database_mongo,
               auth_telegram_initdata, metadata_imdb}/
    features/{catalog_search, streaming, download, mini_app, genre_browsing,
              continue_watching, inline_search, broadcast, statistics,
              notifications, admin_dashboard, channel_access}/
  cache/ttl_cache.py
  server.py                  # composition root: config → provider_registry.get(...) → boot kernel
  config.py
  miniapp/
  tests/{unit,integration}/
  docs/
  Dockerfile
```

---

## 8. Consolidated open decisions (everything accumulated so far, in one place)

1. Database: MongoDB or Postgres as the Phase 1 `DatabaseProvider`?
2. Streaming worker tokens: single bot token or multiple, for the worker pool?
3. Hard $0/month budget, or is a small paid add-on acceptable later?
4. Mini App static hosting preference?
5. Existing Mongo data to migrate, or clean start?
6. Admin surface: in-Telegram only, or also a web dashboard?
7. Plugin scope for Phase 2: minimal set first, or scaffold all listed plugins as stubs now?
8. Build `channel_access` (generic membership gating) now, or leave out until there's a concrete legitimate need?
9. **New:** keep the name `StorageProvider` for file storage and call the new one `DatabaseProvider` (as done above), or swap the names the other way?
10. **New:** license choice — see the open-source structure document for the tradeoffs; this is a legal/strategic choice I won't default silently.
