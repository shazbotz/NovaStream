"""Registers the 'null' StreamingService adapter. Issuing a playback URL
raises ProviderError - there is no streaming engine wired up until a real
adapter is configured. See docs/architecture/streaming.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from media_platform.domain.errors import ProviderError

if TYPE_CHECKING:
    from media_platform.domain.models import PlaybackURL
    from media_platform.kernel.plugin import ProviderContext

_NOT_CONFIGURED = "No StreamingService configured (STREAMING_PROVIDER=null)"


class NullStreamingService:
    async def get_playback_url(
        self, media_id: str, user_id: int, *, expiry_seconds: int = 21600
    ) -> "PlaybackURL":
        raise ProviderError(_NOT_CONFIGURED)

    async def revoke(self, media_id: str, user_id: int) -> None:
        pass


class StreamingNullProviderPlugin:
    name = "provider.streaming.null"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "ProviderContext") -> None:
        ctx.providers.register("streaming", "null", NullStreamingService)


PLUGIN = StreamingNullProviderPlugin()
