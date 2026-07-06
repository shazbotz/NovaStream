"""Catalog orchestration.

Composes the persistence Repository (system of record) with the
SearchProvider (derived, denormalized index) - see
architecture-design-phase1-v3.md §1 for why these are kept as two
separate ports instead of one.
"""

from __future__ import annotations

from media_platform.domain.interfaces import Repository, SearchProvider
from media_platform.domain.models import CatalogItem, QueryFilter, SearchQuery, SearchResult


class CatalogService:
    def __init__(
        self, repository: Repository[CatalogItem], search: SearchProvider
    ) -> None:
        self._repository = repository
        self._search = search

    async def search(self, query: SearchQuery) -> SearchResult:
        return await self._search.search(query)

    async def get_item(self, media_id: str) -> CatalogItem | None:
        return await self._repository.get(media_id)

    async def list_by_genre(
        self, genre: str, *, offset: int = 0, limit: int = 10
    ) -> list[CatalogItem]:
        """Browse the catalog by genre - a direct Repository query, not a
        SearchProvider query, since this is a pure filter/browse with no
        text term (SearchProvider.search() is specifically about ranked
        text search - see docs/architecture/search.md for why these stay
        separate ports). Genre listing/faceting (distinct genre names)
        isn't implemented yet - it would need the Repository interface to
        support a DISTINCT-style operation, which it doesn't today.
        """
        return await self._repository.query(
            QueryFilter(criteria={"genres": genre}, offset=offset, limit=limit)
        )

    async def index_item(self, item: CatalogItem) -> None:
        """Write to the system of record, then update the derived search
        index - two writes, one source of truth. Parsing language/quality/
        season/episode at index time (architecture-design-phase1.md §5) is
        Phase 3 work, done by the ingestion pipeline before this is called.
        """
        await self._repository.save(item)
        await self._search.index(item)

    async def remove_item(self, media_id: str) -> None:
        await self._repository.delete(media_id)
        await self._search.remove(media_id)
