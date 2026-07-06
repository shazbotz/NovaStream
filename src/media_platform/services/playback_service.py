"""Playback orchestration - the Bot's and Mini App's only path to a
playback URL. Neither ever sees a StorageRef or a StreamingService
implementation detail - see architecture-design-phase1-v2.md §2.3.
"""

from __future__ import annotations

from media_platform.domain.interfaces import StreamingService
from media_platform.domain.models import PlaybackURL


class PlaybackService:
    def __init__(self, streaming: StreamingService) -> None:
        self._streaming = streaming

    async def request_playback(
        self, media_id: str, user_id: int, *, expiry_seconds: int = 21600
    ) -> PlaybackURL:
        return await self._streaming.get_playback_url(
            media_id, user_id, expiry_seconds=expiry_seconds
        )

    async def revoke(self, media_id: str, user_id: int) -> None:
        await self._streaming.revoke(media_id, user_id)
