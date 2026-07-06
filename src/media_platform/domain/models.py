"""Domain models.

Plain data structures shared by every layer of the application. This module
must never import anything from ``kernel``, ``services``, ``plugins``, or any
third-party adapter library (Mongo, Pyrogram, aiohttp, ...). It is the one
part of the codebase every other part is allowed to depend on.

See docs/architecture/data-model.md for the reasoning behind each shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utcnow() -> datetime:
    """Single source of truth for 'now', so tests can monkeypatch one place."""
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Catalog / search
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """A search request, transport-agnostic (built the same way whether it
    came from a Telegram message, an inline query, or a Mini App API call).
    """

    text: str
    filters: dict[str, Any] = field(default_factory=dict)
    offset: int = 0
    limit: int = 10

    @classmethod
    def from_text(cls, text: str, **filters: Any) -> "SearchQuery":
        return cls(text=text.strip(), filters=filters)


@dataclass(frozen=True, slots=True)
class SearchHit:
    media_id: str
    score: float
    title: str


@dataclass(frozen=True, slots=True)
class SearchResult:
    """``total`` is exact only when ``has_more`` is False. When there are
    more results than fit in this page, ``total`` is a lower bound
    (``offset + len(hits)``), not necessarily the true total - getting an
    exact total across all pages needs a separate COUNT query, which is
    deliberately not run on every search (see
    docs/design-log/architecture-design-phase1.md §1's note on avoiding
    that exact cost). This supports a "1-10 of at least 11" style UI
    without paying for an exact count nobody asked for.
    """

    hits: list[SearchHit]
    total: int
    has_more: bool


@dataclass(frozen=True, slots=True)
class StorageRef:
    """Opaque, provider-tagged pointer to where a file's bytes live.

    Application code never inspects the payload of a StorageRef beyond
    reading ``provider`` to route to the right StorageProvider adapter -
    everything else is that provider's private business.
    """

    provider: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CatalogItem:
    id: str
    title: str
    file_name: str
    file_size: int
    mime_type: str
    storage_ref: StorageRef
    caption: str = ""
    language: str | None = None
    quality: str | None = None
    codec: str | None = None
    release_type: str | None = None
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    genres: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=utcnow)


# --------------------------------------------------------------------------
# Streaming
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PlaybackURL:
    url: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class FileMetadata:
    size: int
    mime_type: str
    file_name: str


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Credentials:
    """Transport-specific proof of identity, opaque to everything except
    the AuthProvider adapter that knows how to verify it."""

    kind: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    user_id: int
    display_name: str = ""
    roles: tuple[str, ...] = ()


# --------------------------------------------------------------------------
# Metadata enrichment (IMDb and friends)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MetadataResult:
    title: str
    year: int | None
    poster_url: str | None
    rating: float | None
    genres: tuple[str, ...] = ()


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class QueryFilter:
    """Deliberately minimal for the bootstrap phase - grows in Phase 3 when
    a real Repository adapter needs richer querying."""

    criteria: dict[str, Any] = field(default_factory=dict)
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class WatchProgress:
    id: str  # f"{user_id}:{media_id}"
    user_id: int
    media_id: str
    position_seconds: int
    duration_seconds: int = 0
    updated_at: datetime = field(default_factory=utcnow)


# --------------------------------------------------------------------------
# Feature flags
# --------------------------------------------------------------------------


class FlagScope(str, Enum):
    GLOBAL = "global"
    GROUP = "group"
    CHAT = "chat"
    USER = "user"


@dataclass(frozen=True, slots=True)
class FeatureFlag:
    name: str
    global_default: bool = False
    overrides: tuple[tuple[FlagScope, int, bool], ...] = ()


# --------------------------------------------------------------------------
# Telegram gateway
# --------------------------------------------------------------------------


class MemberStatus(str, Enum):
    MEMBER = "member"
    ADMINISTRATOR = "administrator"
    OWNER = "owner"
    LEFT = "left"
    KICKED = "kicked"
    UNKNOWN = "unknown"
