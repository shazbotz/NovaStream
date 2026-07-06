"""Unit tests for media_platform.plugins.providers.storage_telegram.client.

Only covers `RemoteFileRef.from_payload`, the one piece of this adapter
that has no Telegram/network dependency and so can actually run in this
environment. See client.py's module docstring for what remains
unverified (everything that talks to `pyrogram`).
"""

import pytest

from media_platform.plugins.providers.storage_telegram.client import RemoteFileRef


def test_from_payload_parses_valid_ref():
    ref = RemoteFileRef.from_payload({"chat_id": -100123, "message_id": 42})
    assert ref == RemoteFileRef(chat_id=-100123, message_id=42)


def test_from_payload_coerces_string_ints():
    ref = RemoteFileRef.from_payload({"chat_id": "-100123", "message_id": "42"})
    assert ref == RemoteFileRef(chat_id=-100123, message_id=42)


def test_from_payload_rejects_missing_chat_id():
    with pytest.raises(ValueError):
        RemoteFileRef.from_payload({"message_id": 42})


def test_from_payload_rejects_non_integer_message_id():
    with pytest.raises(ValueError):
        RemoteFileRef.from_payload({"chat_id": -100123, "message_id": "not-a-number"})
