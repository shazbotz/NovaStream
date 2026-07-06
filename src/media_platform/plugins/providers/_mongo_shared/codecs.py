"""Explicit (de)serialization between domain models and Mongo documents.

Deliberately explicit rather than a generic dataclass<->dict mapper: with
`from __future__ import annotations` used throughout this codebase,
dataclass field types are strings at runtime, not classes - making a
generic, correct, recursive reconstructor is real complexity for little
benefit at only three models. Explicit codecs are more code, but they are
easy to read, easy to unit test without a live database (pure functions,
no I/O), and don't fail in confusing ways on a type a generic mapper
didn't anticipate.

If a fourth/fifth model shows up and this file grows unwieldy, that's the
signal to revisit - not before.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Generic, TypeVar

from media_platform.domain.models import (
    CatalogItem,
    FeatureFlag,
    FlagScope,
    StorageRef,
    WatchProgress,
)

T = TypeVar("T")


@dataclass(frozen=True)
class Codec(Generic[T]):
    collection_name: str
    to_doc: Callable[[T], dict[str, Any]]
    from_doc: Callable[[dict[str, Any]], T]


# --------------------------------------------------------------------------
# CatalogItem <-> "media" collection
# --------------------------------------------------------------------------


def catalog_item_to_doc(item: CatalogItem) -> dict[str, Any]:
    return {
        "_id": item.id,
        "title": item.title,
        "file_name": item.file_name,
        "file_size": item.file_size,
        "mime_type": item.mime_type,
        "storage_ref": {
            "provider": item.storage_ref.provider,
            "payload": item.storage_ref.payload,
        },
        "caption": item.caption,
        "language": item.language,
        "quality": item.quality,
        "codec": item.codec,
        "release_type": item.release_type,
        "year": item.year,
        "season": item.season,
        "episode": item.episode,
        "genres": list(item.genres),
        "created_at": item.created_at,
    }


def catalog_item_from_doc(doc: dict[str, Any]) -> CatalogItem:
    ref = doc["storage_ref"]
    return CatalogItem(
        id=doc["_id"],
        title=doc["title"],
        file_name=doc["file_name"],
        file_size=doc["file_size"],
        mime_type=doc["mime_type"],
        storage_ref=StorageRef(provider=ref["provider"], payload=ref["payload"]),
        caption=doc.get("caption", ""),
        language=doc.get("language"),
        quality=doc.get("quality"),
        codec=doc.get("codec"),
        release_type=doc.get("release_type"),
        year=doc.get("year"),
        season=doc.get("season"),
        episode=doc.get("episode"),
        genres=tuple(doc.get("genres", [])),
        created_at=doc.get("created_at") or datetime.now(timezone.utc),
    )


# --------------------------------------------------------------------------
# FeatureFlag <-> "feature_flags" collection
# --------------------------------------------------------------------------


def feature_flag_to_doc(flag: FeatureFlag) -> dict[str, Any]:
    return {
        "_id": flag.name,
        "global_default": flag.global_default,
        "overrides": [
            {"scope": scope.value, "id": scoped_id, "enabled": enabled}
            for scope, scoped_id, enabled in flag.overrides
        ],
    }


def feature_flag_from_doc(doc: dict[str, Any]) -> FeatureFlag:
    return FeatureFlag(
        name=doc["_id"],
        global_default=doc.get("global_default", False),
        overrides=tuple(
            (FlagScope(o["scope"]), o["id"], o["enabled"])
            for o in doc.get("overrides", [])
        ),
    )


# --------------------------------------------------------------------------
# WatchProgress <-> "watch_progress" collection
# --------------------------------------------------------------------------


def watch_progress_to_doc(entry: WatchProgress) -> dict[str, Any]:
    return {
        "_id": entry.id,
        "user_id": entry.user_id,
        "media_id": entry.media_id,
        "position_seconds": entry.position_seconds,
        "duration_seconds": entry.duration_seconds,
        "updated_at": entry.updated_at,
    }


def watch_progress_from_doc(doc: dict[str, Any]) -> WatchProgress:
    return WatchProgress(
        id=doc["_id"],
        user_id=doc["user_id"],
        media_id=doc["media_id"],
        position_seconds=doc["position_seconds"],
        duration_seconds=doc.get("duration_seconds", 0),
        updated_at=doc.get("updated_at") or datetime.now(timezone.utc),
    )


CODECS: dict[str, Codec[Any]] = {
    "media": Codec("media", catalog_item_to_doc, catalog_item_from_doc),
    "feature_flags": Codec("feature_flags", feature_flag_to_doc, feature_flag_from_doc),
    "watch_progress": Codec("watch_progress", watch_progress_to_doc, watch_progress_from_doc),
}
