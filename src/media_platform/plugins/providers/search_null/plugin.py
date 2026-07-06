"""Registers the 'null' SearchProvider adapter - always returns empty
results. Default in development so the app can boot without a real search
backend configured. Replace with a real adapter (mongo_text, meilisearch,
...) in Phase 3 - see docs/architecture/search.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from media_platform.domain.models import SearchResult

if TYPE_CHECKING:
    from media_platform.domain.models import CatalogItem, SearchQuery
    from media_platform.kernel.plugin import ProviderContext


class NullSearchProvider:
    async def index(self, doc: "CatalogItem") -> None:
        pass

    async def remove(self, doc_id: str) -> None:
        pass

    async def search(self, query: "SearchQuery") -> SearchResult:
        return SearchResult(hits=[], total=0, has_more=False)

    async def suggest(self, prefix: str, limit: int = 10) -> list[str]:
        return []


class SearchNullProviderPlugin:
    name = "provider.search.null"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "ProviderContext") -> None:
        ctx.providers.register("search", "null", NullSearchProvider)


PLUGIN = SearchNullProviderPlugin()
