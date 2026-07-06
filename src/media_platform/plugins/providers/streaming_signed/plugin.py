"""Registers the 'signed' StreamingService adapter.

Implements the signed, expiring stream-URL scheme specified in
`docs/design-log/architecture-design-phase1.md` §4.3 and
`docs/architecture/streaming.md`, using the pure HMAC helper in
`services/stream_tokens.py` so the signing logic here and the
verification logic in the raw `/stream/{media_id}` HTTP handler
(registered directly by `server.py`, next to `/healthz`) can never drift
apart.

This adapter only *issues URLs* - it does not serve bytes. Actually
reading a range of a file still goes through whatever `StorageProvider`
is configured (e.g. `storage_telegram`); `get_playback_url()` here never
touches storage, so it stays a cheap, synchronous-feeling call with no
I/O of its own, same shape as `NullStreamingService`.

`revoke()` is deliberately a no-op: a stateless HMAC URL cannot be
invalidated before its own expiry without a server-side revocation list,
which would need a shared cache this provider isn't given (providers only
receive `ProviderContext`, not `ServiceLocator` - see
`kernel/plugin.py`). Short TTLs (`STREAM_URL_EXPIRY_SECONDS`, default 6h)
are the mitigation, exactly as scoped in the design doc. A future
revocation list is a `services/`-level addition layered on top of this,
not a change to this file's contract.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from media_platform.domain.errors import ConfigurationError
from media_platform.domain.models import PlaybackURL
from media_platform.services import stream_tokens

if TYPE_CHECKING:
    from media_platform.kernel.plugin import ProviderContext


class SignedStreamingService:
    def __init__(self, secret: str, base_url: str) -> None:
        self._secret = secret
        self._base_url = base_url.rstrip("/")

    async def get_playback_url(
        self, media_id: str, user_id: int, *, expiry_seconds: int = 21600
    ) -> PlaybackURL:
        expires_at_ts = int(time.time()) + expiry_seconds
        signature = stream_tokens.sign(self._secret, media_id, user_id, expires_at_ts)
        url = (
            f"{self._base_url}/stream/{media_id}"
            f"?exp={expires_at_ts}&sig={signature}&u={user_id}"
        )
        expires_at = datetime.fromtimestamp(expires_at_ts, tz=timezone.utc)
        return PlaybackURL(url=url, expires_at=expires_at)

    async def revoke(self, media_id: str, user_id: int) -> None:
        # See module docstring - stateless URLs, nothing to revoke here.
        pass


class StreamingSignedProviderPlugin:
    name = "provider.streaming.signed"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "ProviderContext") -> None:
        def build() -> SignedStreamingService:
            if not ctx.config.stream_secret:
                raise ConfigurationError(
                    "STREAMING_PROVIDER=signed requires STREAM_SECRET to be set"
                )
            return SignedStreamingService(
                secret=ctx.config.stream_secret,
                base_url=ctx.config.public_base_url,
            )

        ctx.providers.register("streaming", "signed", build)


PLUGIN = StreamingSignedProviderPlugin()
