"""catalog_search feature plugin - the first feature plugin, and the
reference example for `docs/guides/plugin-development.md`.

Registers:
- ``GET /api/search``  - search the catalog, results grouped by title+year
  (see grouping.py) so a movie with 5 file variants shows as one entry,
  not five
- ``POST /api/media``  - register a media item (calls
  `CatalogService.index_item`), authenticated
- a ``search`` bot command, transport-agnostic - takes plain args and a
  `reply` callback rather than any Telegram-specific message object

Both the HTTP route and the bot command call the exact same
`CatalogService.search()` - this is the API-first rule
(architecture-design-phase1-v3.md §4) made concrete: whichever transport
gets a new client type later (Web Dashboard, Desktop, Mobile), the search
behavior lives in exactly one place. Grouping (grouping.py) is applied
identically on both transports for the same reason - the "search
result grouped by movie, single-variant skips straight to details" logic
isn't allowed to drift between them.

Deliberately NOT implemented here, named rather than silently skipped:
- The channel-scanning ingestion pipeline that would pull files
  automatically from a Telegram channel's history. `POST /api/media` is a
  direct, manual/admin indexing endpoint for now - see
  docs/design-log/architecture-design-phase1.md §5 for the eventual
  producer/consumer ingestion design this is expected to grow into.
- Wiring `cmd_search` to a live Telegram client, or wiring the "select
  language -> select quality" flow into actual Telegram inline keyboards.
  The grouping data (languages/qualities/variants) is all there in the
  response `cmd_search` builds; turning that into buttons needs the bot
  polling loop and `CallbackRegistry` wiring, which is a separate,
  deferred piece of work - see plugins/providers/telegram_kurigram's
  docstring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable, Iterable

from media_platform.domain.errors import ValidationError
from media_platform.domain.interfaces import AuthProvider
from media_platform.domain.models import CatalogItem, SearchQuery, StorageRef
from media_platform.kernel.api_router import ApiRequest, ApiResponse, parse_query_int
from media_platform.plugins.features.catalog_search.grouping import (
    GroupedTitle,
    group_catalog_items,
)
from media_platform.services.auth_helper import bearer_credentials, require_authenticated
from media_platform.services.catalog_service import CatalogService

if TYPE_CHECKING:
    from media_platform.kernel.plugin import PluginContext

Reply = Callable[[str], Awaitable[None]]

_MAX_SEARCH_LIMIT = 50  # a query parameter the caller controls shouldn't
# be able to force an unbounded amount of work - see
# docs/guides/performance.md.


class CatalogSearchPlugin:
    name = "feature.catalog_search"
    version = "0.2.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "PluginContext") -> None:
        # Bind exactly what this plugin needs, not the whole context -
        # `ctx.providers`/`ctx.scheduler`/etc. aren't this plugin's
        # business once registration is done.
        self._catalog: CatalogService = ctx.services.catalog
        self._auth: AuthProvider = ctx.services.auth

        ctx.api.get("/api/search", self.api_search)
        ctx.api.post("/api/media", self.api_index_media)
        ctx.commands.register("search", self.cmd_search)

    # --- HTTP transport ----------------------------------------------------

    async def api_search(self, request: ApiRequest) -> ApiResponse:
        query_text = request.query.get("q", "").strip()
        offset = parse_query_int(request.query, "offset", default=0)
        limit = min(parse_query_int(request.query, "limit", default=10), _MAX_SEARCH_LIMIT)

        result = await self._catalog.search(
            SearchQuery(text=query_text, offset=offset, limit=limit)
        )
        items = await self._fetch_items(hit.media_id for hit in result.hits)
        groups = group_catalog_items(items)

        return ApiResponse(
            body={
                "results": [_group_to_dict(group) for group in groups],
                "total": result.total,
                "has_more": result.has_more,
            }
        )

    async def api_index_media(self, request: ApiRequest) -> ApiResponse:
        await require_authenticated(self._auth, bearer_credentials(request.headers))
        item = _catalog_item_from_request_body(request.body or {})
        await self._catalog.index_item(item)
        return ApiResponse(body={"id": item.id}, status=201)

    async def _fetch_items(self, media_ids: Iterable[str]) -> list[CatalogItem]:
        items: list[CatalogItem] = []
        for media_id in media_ids:
            item = await self._catalog.get_item(media_id)
            if item is not None:
                items.append(item)
        return items

    # --- Bot transport -------------------------------------------------------

    async def cmd_search(self, args: str, reply: Reply) -> None:
        query_text = args.strip()
        if not query_text:
            await reply("Usage: /search <text>")
            return

        result = await self._catalog.search(SearchQuery.from_text(query_text))
        if not result.hits:
            await reply(f"No results for '{query_text}'.")
            return

        items = await self._fetch_items(hit.media_id for hit in result.hits)
        groups = group_catalog_items(items)

        lines = [f"Results for '{query_text}':"]
        for group in groups:
            lines.append(_format_group_line(group))
        if result.has_more:
            lines.append("(more results available)")
        await reply("\n".join(lines))


def _format_group_line(group: GroupedTitle) -> str:
    title = f"{group.title} ({group.year})" if group.year else group.title
    if group.is_single_variant:
        # Only one version exists - skip the language/quality selection
        # step and show what you'd get directly, per this enhancement's
        # requirement.
        variant = group.variants[0]
        details = ", ".join(filter(None, [variant.language, variant.quality]))
        return f"- {title} - {details}" if details else f"- {title}"

    return (
        f"- {title} - {len(group.variants)} versions "
        f"(languages: {', '.join(group.languages) or 'n/a'}; "
        f"qualities: {', '.join(group.qualities) or 'n/a'})"
    )


def _group_to_dict(group: GroupedTitle) -> dict[str, Any]:
    return {
        "title": group.title,
        "year": group.year,
        "variant_count": len(group.variants),
        "languages": group.languages,
        "qualities": group.qualities,
        "variants": [
            {
                "media_id": v.media_id,
                "language": v.language,
                "quality": v.quality,
                "codec": v.codec,
                "release_type": v.release_type,
                "file_size": v.file_size,
            }
            for v in group.variants
        ],
    }


def _catalog_item_from_request_body(body: dict[str, Any]) -> CatalogItem:
    required = ("id", "title", "file_name", "file_size", "mime_type", "storage_ref")
    missing = [field for field in required if not body.get(field)]
    if missing:
        raise ValidationError(f"Missing required field(s): {', '.join(missing)}")

    ref = body["storage_ref"]
    if not isinstance(ref, dict) or "provider" not in ref or "payload" not in ref:
        raise ValidationError("'storage_ref' must be an object with 'provider' and 'payload'")

    try:
        file_size = int(body["file_size"])
    except (TypeError, ValueError) as exc:
        raise ValidationError("'file_size' must be an integer") from exc

    year = body.get("year")
    if year is not None:
        try:
            year = int(year)
        except (TypeError, ValueError) as exc:
            raise ValidationError("'year' must be an integer") from exc

    genres_raw = body.get("genres", [])
    if not isinstance(genres_raw, list):
        raise ValidationError("'genres' must be a list of strings")

    return CatalogItem(
        id=str(body["id"]),
        title=str(body["title"]),
        file_name=str(body["file_name"]),
        file_size=file_size,
        mime_type=str(body["mime_type"]),
        storage_ref=StorageRef(provider=ref["provider"], payload=ref["payload"]),
        caption=str(body.get("caption", "")),
        language=body.get("language"),
        quality=body.get("quality"),
        codec=body.get("codec"),
        release_type=body.get("release_type"),
        year=year,
        season=body.get("season"),
        episode=body.get("episode"),
        genres=tuple(str(g) for g in genres_raw),
    )


PLUGIN = CatalogSearchPlugin()
