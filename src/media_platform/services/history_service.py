"""Watch-progress orchestration (Continue Watching).

Ranking/trimming logic for `continue_watching()` (recency, in-progress vs.
finished, etc.) is Phase 3 feature work - this wires the repository
correctly and returns what's stored.
"""

from __future__ import annotations

from media_platform.domain.interfaces import Repository
from media_platform.domain.models import QueryFilter, WatchProgress


class HistoryService:
    def __init__(self, repository: Repository[WatchProgress]) -> None:
        self._repository = repository

    async def record_progress(
        self, user_id: int, media_id: str, position_seconds: int, duration_seconds: int = 0
    ) -> None:
        entry = WatchProgress(
            id=f"{user_id}:{media_id}",
            user_id=user_id,
            media_id=media_id,
            position_seconds=position_seconds,
            duration_seconds=duration_seconds,
        )
        await self._repository.save(entry)

    async def continue_watching(self, user_id: int) -> list[WatchProgress]:
        return await self._repository.query(QueryFilter(criteria={"user_id": user_id}))
