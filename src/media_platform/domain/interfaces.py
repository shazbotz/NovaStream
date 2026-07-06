"""Core interfaces (ports), in the ports-and-adapters sense.

Every one of these is a :class:`typing.Protocol` - structural typing, so an
adapter conforms simply by having the right methods, with no inheritance
requirement. ``services`` and ``plugins`` are only ever allowed to depend on
the interfaces in this file, never on a concrete adapter class.

Concrete adapters live under ``plugins/providers/<name>/`` and register
themselves into the :class:`~media_platform.kernel.provider_registry.ProviderRegistry`
under one of the port names below (``"search"``, ``"storage"``, ``"database"``,
``"auth"``, ``"metadata"``, ``"streaming"``).

Each Protocol is intentionally small. Business logic (ranking, retry policy,
caching, orchestration) belongs in ``services/``, not here.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Protocol, TypeVar, runtime_checkable

from media_platform.domain.models import (
    AuthenticatedPrincipal,
    CatalogItem,
    Credentials,
    FeatureFlag,
    FileMetadata,
    FlagScope,
    MemberStatus,
    MetadataResult,
    PlaybackURL,
    QueryFilter,
    SearchQuery,
    SearchResult,
    StorageRef,
)

T = TypeVar("T")


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------


@runtime_checkable
class SearchProvider(Protocol):
    """A queryable, ranked index over the catalog.

    Deliberately separate from :class:`Repository` - the search index is a
    derived, denormalized view that may live in a different system than the
    catalog's system of record (see docs/architecture/search.md).
    """

    async def index(self, doc: CatalogItem) -> None: ...

    async def remove(self, doc_id: str) -> None: ...

    async def search(self, query: SearchQuery) -> SearchResult: ...

    async def suggest(self, prefix: str, limit: int = 10) -> list[str]: ...


# --------------------------------------------------------------------------
# File storage (where media bytes live - Telegram, S3, R2, B2, local, ...)
# --------------------------------------------------------------------------


@runtime_checkable
class StorageProvider(Protocol):
    """Abstracts *where file bytes live*. Not to be confused with
    :class:`DatabaseProvider`, which abstracts where structured records
    live. See docs/architecture/storage.md for why these are separate.
    """

    async def put(self, key: str, source: AsyncIterator[bytes]) -> StorageRef: ...

    async def get_range(
        self, ref: StorageRef, start: int, end: int
    ) -> AsyncIterator[bytes]: ...

    async def get_metadata(self, ref: StorageRef) -> FileMetadata: ...

    async def delete(self, ref: StorageRef) -> None: ...


# --------------------------------------------------------------------------
# Streaming
# --------------------------------------------------------------------------


@runtime_checkable
class StreamingService(Protocol):
    """The *entire* surface the Bot and Mini App are allowed to know about
    for playback. No caller of this interface ever sees a StorageRef, a
    worker pool, or a chunk size - see docs/architecture/streaming.md.
    """

    async def get_playback_url(
        self, media_id: str, user_id: int, *, expiry_seconds: int = 21600
    ) -> PlaybackURL: ...

    async def revoke(self, media_id: str, user_id: int) -> None: ...


# --------------------------------------------------------------------------
# Persistence (structured records: catalog, users, watch history, flags)
# --------------------------------------------------------------------------


@runtime_checkable
class Repository(Protocol[T]):
    """One repository per aggregate (media, users, watch_progress, ...).
    Obtained from a :class:`DatabaseProvider` by name - never instantiated
    directly by a service.
    """

    async def get(self, id: str) -> T | None: ...

    async def save(self, entity: T) -> None: ...

    async def delete(self, id: str) -> None: ...

    async def query(self, query_filter: QueryFilter) -> list[T]: ...


@runtime_checkable
class DatabaseProvider(Protocol):
    """Owns connection lifecycle and hands out named repositories.

    Renamed from the reference document's "StorageProvider" to avoid a
    name collision with the file-storage interface above - see
    docs/architecture/storage.md and architecture-design-phase1-v3.md §0.
    """

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    def repository(self, name: str) -> Repository[Any]: ...


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------


@runtime_checkable
class AuthProvider(Protocol):
    async def authenticate(
        self, credentials: Credentials
    ) -> AuthenticatedPrincipal | None: ...


# --------------------------------------------------------------------------
# Metadata enrichment (IMDb and friends)
# --------------------------------------------------------------------------


@runtime_checkable
class MetadataProvider(Protocol):
    async def lookup(
        self, title: str, year: int | None = None
    ) -> MetadataResult | None: ...


# --------------------------------------------------------------------------
# Telegram access (cache -> database -> Telegram API, centralized)
# --------------------------------------------------------------------------


@runtime_checkable
class TelegramGateway(Protocol):
    """The *only* permitted path to the Telegram API. No plugin or service
    is given a raw client reference - see docs/architecture/overview.md.
    """

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def get_chat_member(self, chat_id: int, user_id: int) -> MemberStatus: ...

    async def get_messages(self, chat_id: int, message_ids: list[int]) -> list[Any]: ...

    async def send_message(self, chat_id: int, text: str, **kwargs: Any) -> Any: ...


# --------------------------------------------------------------------------
# Feature flags
# --------------------------------------------------------------------------


@runtime_checkable
class FeatureFlags(Protocol):
    async def is_enabled(
        self,
        feature: str,
        *,
        user_id: int | None = None,
        chat_id: int | None = None,
        group_id: int | None = None,
    ) -> bool: ...

    async def set(
        self,
        feature: str,
        enabled: bool,
        *,
        scope: FlagScope,
        scope_id: int | None = None,
    ) -> None: ...

    async def get(self, feature: str) -> FeatureFlag | None: ...
