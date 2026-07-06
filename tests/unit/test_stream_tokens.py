"""Unit tests for media_platform.services.stream_tokens.

Pure HMAC logic, no I/O - covers the signature scheme documented in
docs/design-log/architecture-design-phase1.md §4.3.
"""

from media_platform.services import stream_tokens


def test_sign_is_deterministic():
    sig1 = stream_tokens.sign("secret", "media-1", 42, 1700000000)
    sig2 = stream_tokens.sign("secret", "media-1", 42, 1700000000)
    assert sig1 == sig2


def test_verify_accepts_matching_signature():
    sig = stream_tokens.sign("secret", "media-1", 42, 1700000000)
    assert stream_tokens.verify("secret", "media-1", 42, 1700000000, sig) is True


def test_verify_rejects_tampered_media_id():
    sig = stream_tokens.sign("secret", "media-1", 42, 1700000000)
    assert stream_tokens.verify("secret", "media-2", 42, 1700000000, sig) is False


def test_verify_rejects_tampered_user_id():
    sig = stream_tokens.sign("secret", "media-1", 42, 1700000000)
    assert stream_tokens.verify("secret", "media-1", 99, 1700000000, sig) is False


def test_verify_rejects_tampered_expiry():
    sig = stream_tokens.sign("secret", "media-1", 42, 1700000000)
    assert stream_tokens.verify("secret", "media-1", 42, 1700000999, sig) is False


def test_verify_rejects_wrong_secret():
    sig = stream_tokens.sign("secret", "media-1", 42, 1700000000)
    assert stream_tokens.verify("other-secret", "media-1", 42, 1700000000, sig) is False


def test_verify_rejects_garbage_signature():
    assert stream_tokens.verify("secret", "media-1", 42, 1700000000, "not-a-real-sig") is False
