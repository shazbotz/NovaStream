"""genre_browsing feature plugin.

Registers:
- ``GET /api/genres/{genre}``  - items tagged with the given genre (calls
  `CatalogService.list_by_genre`)

Deliberately NOT implemented here:
- ``GET /api/genres`` (list all distinct genre names) - the `Repository`
  interface doesn't support a DISTINCT-style operation today, and adding
  one just for this would mean changing a core port for a single feature
  plugin's convenience. A client that already knows genre names (e.g. a
  fixed list shown in the Mini App) can call the per-genre route directly;
  a real "list all genres" endpoint is a reasonable follow-up once it's
  needed by more than one caller.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from media_platform.domain.errors import ValidationError
from media_platform.kernel.api_router import ApiRequest, ApiResponse, parse_query_int
from media_platform.services.catalog_service import CatalogService

if TYPE_CHECKING:
    from media_platform.kernel.plugin import PluginContext

_MAX_LIMIT = 50


class GenreBrowsingPlugin:
    name = "feature.genre_browsing"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "PluginContext") -> None:
        self._catalog: CatalogService = ctx.services.catalog
        ctx.api.get("/api/genres/{genre}", self.api_by_genre)

    async def api_by_genre(self, request: ApiRequest) -> ApiResponse:
        genre = request.path_params.get("genre", "").strip()
        if not genre:
            raise ValidationError("genre is required")

        offset = parse_query_int(request.query, "offset", default=0)
        limit = min(parse_query_int(request.query, "limit", default=10), _MAX_LIMIT)

        items = await self._catalog.list_by_genre(genre, offset=offset, limit=limit)
        return ApiResponse(
            body={
                "genre": genre,
                "items": [
                    {"media_id": item.id, "title": item.title, "year": item.year}
                    for item in items
                ],
            }
        )


PLUGIN = GenreBrowsingPlugin()
