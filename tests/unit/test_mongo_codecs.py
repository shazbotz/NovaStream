"""Unit tests for the Mongo (de)serialization codecs.

Pure-function tests - no live MongoDB connection needed, which is exactly
why these codecs are written as plain functions instead of being buried
inside methods that also do I/O. This is the part of a Mongo adapter most
worth testing directly: the actual `motor` calls are thin, well-documented
wrappers; getting the round-trip shape right (nested StorageRef, Enum
scopes, datetimes) is where real bugs hide.
"""

from media_platform.domain.models import (
    CatalogItem,
    FeatureFlag,
    FlagScope,
    StorageRef,
    WatchProgress,
)
from media_platform.plugins.providers._mongo_shared.codecs import (
    catalog_item_from_doc,
    catalog_item_to_doc,
    feature_flag_from_doc,
    feature_flag_to_doc,
    watch_progress_from_doc,
    watch_progress_to_doc,
)


def test_catalog_item_round_trip():
    item = CatalogItem(
        id="abc",
        title="Sample",
        file_name="sample.mkv",
        file_size=1024,
        mime_type="video/x-matroska",
        storage_ref=StorageRef(
            provider="telegram", payload={"chat_id": -100123, "message_id": 5}
        ),
        caption="a caption",
        language="en",
        quality="1080p",
        season=1,
        episode=2,
    )
    doc = catalog_item_to_doc(item)
    assert doc["_id"] == "abc"  # Mongo's primary key field
    assert doc["storage_ref"] == {
        "provider": "telegram",
        "payload": {"chat_id": -100123, "message_id": 5},
    }
    assert catalog_item_from_doc(doc) == item


def test_catalog_item_round_trip_with_optional_fields_absent():
    item = CatalogItem(
        id="abc",
        title="Sample",
        file_name="sample.mkv",
        file_size=1024,
        mime_type="video/mp4",
        storage_ref=StorageRef(provider="telegram", payload={}),
    )
    doc = catalog_item_to_doc(item)
    assert catalog_item_from_doc(doc) == item


def test_feature_flag_round_trip_with_no_overrides():
    flag = FeatureFlag(name="mini_app", global_default=True)
    doc = feature_flag_to_doc(flag)
    assert doc["_id"] == "mini_app"
    assert doc["overrides"] == []
    assert feature_flag_from_doc(doc) == flag


def test_feature_flag_round_trip_with_scoped_overrides():
    flag = FeatureFlag(
        name="mini_app",
        global_default=True,
        overrides=(
            (FlagScope.USER, 42, False),
            (FlagScope.CHAT, -100, True),
        ),
    )
    doc = feature_flag_to_doc(flag)
    # Enum is stored as its plain string value, not a Python object -
    # this is what makes the document safe to store/inspect in Mongo.
    assert doc["overrides"][0] == {"scope": "user", "id": 42, "enabled": False}
    assert feature_flag_from_doc(doc) == flag


def test_watch_progress_round_trip():
    entry = WatchProgress(
        id="1:abc", user_id=1, media_id="abc", position_seconds=90, duration_seconds=5400
    )
    doc = watch_progress_to_doc(entry)
    assert doc["_id"] == "1:abc"
    assert watch_progress_from_doc(doc) == entry


def test_watch_progress_from_doc_defaults_duration_when_absent():
    doc = {"_id": "1:abc", "user_id": 1, "media_id": "abc", "position_seconds": 5}
    entry = watch_progress_from_doc(doc)
    assert entry.duration_seconds == 0
