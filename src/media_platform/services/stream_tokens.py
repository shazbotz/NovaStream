"""Signed, expiring stream-URL tokens.

Implements the scheme specified (but not yet built) in
`docs/design-log/architecture-design-phase1.md` §4.3::

    token = HMAC-SHA256(secret, f"{media_id}:{user_id}:{expiry_ts}")
    url   = /stream/{media_id}?exp={expiry_ts}&sig={token}&u={user_id}

Deliberately pure functions with no I/O and no third-party imports - the
whole point of pulling this out of the `streaming_signed` provider plugin
and the raw `/stream` HTTP handler is that both sides (issuing a token,
verifying one) share exactly one implementation of the signature, and
that implementation is trivially unit-testable without a database, an
HTTP server, or a Telegram client.

This module lives in `services/` (not `domain/`) because it's shared
behavior *used by* a provider plugin and by the composition root, not a
plain data shape - but it must never import from `kernel/` or
`plugins/`, same rule as every other module under `services/` (enforced
by `pyproject.toml`'s `[tool.importlinter]` contracts).
"""

from __future__ import annotations

import hashlib
import hmac


def _digest(secret: str, media_id: str, user_id: int, expires_at: int) -> str:
    message = f"{media_id}:{user_id}:{expires_at}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def sign(secret: str, media_id: str, user_id: int, expires_at: int) -> str:
    """Returns the hex-encoded HMAC-SHA256 signature for these fields."""
    return _digest(secret, media_id, user_id, expires_at)


def verify(
    secret: str, media_id: str, user_id: int, expires_at: int, signature: str
) -> bool:
    """Constant-time comparison against a freshly computed signature.

    Does NOT check expiry - that's a separate, plain integer comparison
    the caller does against "now" (kept out of this function so it stays
    pure and doesn't need `domain.models.utcnow`, and so tests don't need
    to freeze time to check the signature check itself).
    """
    expected = _digest(secret, media_id, user_id, expires_at)
    return hmac.compare_digest(expected, signature)
