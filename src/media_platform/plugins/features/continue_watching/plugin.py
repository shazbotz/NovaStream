"""continue_watching feature plugin.

Registers:
- ``GET /api/continue-watching``  - the authenticated caller's in-progress
  items (calls `HistoryService.continue_watching`)
- ``POST /api/watch-progress``    - record playback position (calls
  `HistoryService.record_progress`)

Both routes require authentication and use the authenticated principal's
`user_id` - never a client-supplied one from the query string or request
body. Without this, one user could read or overwrite another user's watch
history simply by passing a different `user_id` value; see
`services/auth_helper.py`'s docstring for the same reasoning applied here.

Deliberately NOT implemented here:
- Trimming/ranking logic for what counts as "in progress" vs "finished"
  (e.g. hiding items past 95% watched) - `HistoryService.continue_watching`
  currently returns everything recorded for the user, unfiltered. This is
  presentation/ranking logic that can be layered on without touching this
  plugin's route contract - not built yet, named rather than hidden.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from media_platform.domain.errors import ValidationError
from media_platform.domain.interfaces import AuthProvider
from media_platform.kernel.api_router import ApiRequest, ApiResponse
from media_platform.services.auth_helper import bearer_credentials, require_authenticated
from media_platform.services.history_service import HistoryService

if TYPE_CHECKING:
    from media_platform.kernel.plugin import PluginContext


class ContinueWatchingPlugin:
    name = "feature.continue_watching"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "PluginContext") -> None:
        self._history: HistoryService = ctx.services.history
        self._auth: AuthProvider = ctx.services.auth

        ctx.api.get("/api/continue-watching", self.api_continue_watching)
        ctx.api.post("/api/watch-progress", self.api_record_progress)

    async def api_continue_watching(self, request: ApiRequest) -> ApiResponse:
        principal = await require_authenticated(self._auth, bearer_credentials(request.headers))
        entries = await self._history.continue_watching(principal.user_id)
        return ApiResponse(
            body={
                "items": [
                    {
                        "media_id": e.media_id,
                        "position_seconds": e.position_seconds,
                        "duration_seconds": e.duration_seconds,
                    }
                    for e in entries
                ]
            }
        )

    async def api_record_progress(self, request: ApiRequest) -> ApiResponse:
        principal = await require_authenticated(self._auth, bearer_credentials(request.headers))
        body = request.body or {}

        media_id = body.get("media_id")
        if not media_id:
            raise ValidationError("Missing required field: media_id")

        position_seconds = _require_non_negative_int(body, "position_seconds")
        duration_seconds = _optional_non_negative_int(body, "duration_seconds", default=0)

        await self._history.record_progress(
            user_id=principal.user_id,
            media_id=str(media_id),
            position_seconds=position_seconds,
            duration_seconds=duration_seconds,
        )
        return ApiResponse(body={"status": "ok"}, status=200)


def _require_non_negative_int(body: dict[str, Any], key: str) -> int:
    if key not in body:
        raise ValidationError(f"Missing required field: {key}")
    return _optional_non_negative_int(body, key, default=0, required=True)


def _optional_non_negative_int(
    body: dict[str, Any], key: str, *, default: int, required: bool = False
) -> int:
    raw = body.get(key, default if not required else None)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"'{key}' must be an integer") from exc
    if value < 0:
        raise ValidationError(f"'{key}' must not be negative")
    return value


PLUGIN = ContinueWatchingPlugin()
