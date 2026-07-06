"""streaming feature plugin.

Registers:
- ``GET /api/stream-token/{media_id}``   - issue a signed, expiring
  playback URL for in-app streaming (calls `PlaybackService.request_playback`)
- ``GET /api/download-token/{media_id}`` - issue the same kind of URL,
  tagged so the raw `/stream/{media_id}` HTTP handler (registered
  directly by `server.py`, see its docstring) sends
  ``Content-Disposition: attachment`` instead of an inline response -
  this is what powers both "Streaming" and "Download"/"Offline Download"
  from the same signed-URL mechanism, per
  `docs/design-log/architecture-design-phase1.md` §4.3's single
  `/stream/{file_id}` endpoint design.

Both routes require authentication and use the authenticated principal's
`user_id` - same reasoning as `continue_watching/plugin.py`'s docstring:
a playback URL is minted for *this* caller, never for a client-supplied
user id.

Deliberately NOT implemented here:
- Actually serving file bytes. That happens in the raw
  `/stream/{media_id}` aiohttp handler registered by `server.py`
  (verifies the signature from `services/stream_tokens.py`, then reads
  from whichever `StorageProvider` is configured) - a binary,
  Range-header-aware response is outside what `ApiRouter`'s
  `ApiRequest`/`ApiResponse` (JSON-only) can express, same reason
  `/healthz` is also registered directly on the aiohttp app rather than
  through `ApiRouter`. See `docs/architecture/streaming.md`.
- A server-side "recent downloads" ledger distinct from watch history -
  `continue_watching`'s `watch_progress` collection already covers
  "what has this user watched/how far"; a separate downloaded-files list
  is presentation-layer bookkeeping the Mini App can keep client-side for
  now (see `miniapp/src/pages/Downloads` if present).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from media_platform.domain.errors import NotFoundError, ValidationError
from media_platform.domain.interfaces import AuthProvider
from media_platform.kernel.api_router import ApiRequest, ApiResponse
from media_platform.services.auth_helper import bearer_credentials, require_authenticated
from media_platform.services.catalog_service import CatalogService
from media_platform.services.playback_service import PlaybackService

if TYPE_CHECKING:
    from media_platform.kernel.plugin import PluginContext


class StreamingPlugin:
    name = "feature.streaming"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "PluginContext") -> None:
        self._catalog: CatalogService = ctx.services.catalog
        self._playback: PlaybackService = ctx.services.playback
        self._auth: AuthProvider = ctx.services.auth

        ctx.api.get("/api/stream-token/{media_id}", self.api_stream_token)
        ctx.api.get("/api/download-token/{media_id}", self.api_download_token)

    async def api_stream_token(self, request: ApiRequest) -> ApiResponse:
        return await self._issue_token(request, download=False)

    async def api_download_token(self, request: ApiRequest) -> ApiResponse:
        return await self._issue_token(request, download=True)

    async def _issue_token(self, request: ApiRequest, *, download: bool) -> ApiResponse:
        principal = await require_authenticated(self._auth, bearer_credentials(request.headers))

        media_id = request.path_params.get("media_id", "").strip()
        if not media_id:
            raise ValidationError("media_id is required")

        item = await self._catalog.get_item(media_id)
        if item is None:
            raise NotFoundError(f"No media item with id '{media_id}'")

        playback_url = await self._playback.request_playback(media_id, principal.user_id)
        url = playback_url.url + ("&dl=1" if download else "")
        return ApiResponse(
            body={
                "url": url,
                "expires_at": playback_url.expires_at.isoformat(),
                "file_name": item.file_name,
                "file_size": item.file_size,
                "mime_type": item.mime_type,
            }
        )


PLUGIN = StreamingPlugin()
