"""Mongo `$text`-index-backed SearchProvider.

Replaces the infix-regex full-collection-scan search found in the
reference bots (docs/design-log/architecture-design-phase1.md §1) with a
native, tokenized, indexed text search - available on every MongoDB tier,
including free, with no extra service to run.

Same verification caveat as `database_mongo/provider.py`: written
carefully against motor's well-documented, stable API, but not
executable in the environment this was written in (no `motor` installed,
no live MongoDB) - treat as reviewed-but-not-yet-integration-tested. See
tests/integration/README.md.

Known, accepted inefficiency: this constructs its own MongoDB client
connection, separate from `database_mongo`'s, even though both typically
point at the same server when `SEARCH_PROVIDER=mongo_text` and
`DATABASE_PROVIDER=mongo` are both selected. Sharing one client across
both ports would need a small connection-cache keyed by URL - worth doing
once there's a real reason to (e.g. connection-count pressure on a free
Atlas tier), not before. Flagged here rather than silently accepted.
"""

from __future__ import annotations

from typing import Any

import motor.motor_asyncio

from media_platform.domain.models import CatalogItem, SearchHit, SearchQuery, SearchResult
from media_platform.plugins.providers._mongo_shared.codecs import catalog_item_to_doc


class MongoSearchProvider:
    def __init__(self, url: str, db_name: str = "media_platform") -> None:
        self._client: Any = motor.motor_asyncio.AsyncIOMotorClient(url)
        self._collection = self._client[db_name]["media"]

    async def index(self, doc: CatalogItem) -> None:
        document = catalog_item_to_doc(doc)
        await self._collection.replace_one({"_id": document["_id"]}, document, upsert=True)

    async def remove(self, doc_id: str) -> None:
        await self._collection.delete_one({"_id": doc_id})

    async def search(self, query: SearchQuery) -> SearchResult:
        if not query.text:
            return SearchResult(hits=[], total=0, has_more=False)

        mongo_filter: dict[str, Any] = {"$text": {"$search": query.text}}
        mongo_filter.update(query.filters)

        projection = {"score": {"$meta": "textScore"}}
        cursor = (
            self._collection.find(mongo_filter, projection)
            .sort([("score", {"$meta": "textScore"})])
            .skip(query.offset)
            .limit(query.limit + 1)  # fetch one extra row to derive has_more cheaply
        )
        docs = [doc async for doc in cursor]

        has_more = len(docs) > query.limit
        docs = docs[: query.limit]
        hits = [
            SearchHit(media_id=doc["_id"], score=doc.get("score", 0.0), title=doc["title"])
            for doc in docs
        ]
        # Exact when not has_more; a lower bound otherwise - see
        # SearchResult's docstring for why an exact cross-page total
        # isn't computed here (it would need a separate COUNT query on
        # every search).
        total = query.offset + len(hits)
        return SearchResult(hits=hits, total=total, has_more=has_more)

    async def suggest(self, prefix: str, limit: int = 10) -> list[str]:
        if not prefix:
            return []
        # Naive prefix match on file_name for now - this is exactly the
        # seam docs/architecture/search.md describes for a future
        # Meilisearch/Typesense/Atlas Search adapter to do properly
        # (fuzzy, typo-tolerant, ranked autocomplete) without any
        # CatalogService change.
        cursor = self._collection.find(
            {"file_name": {"$regex": f"^{prefix}", "$options": "i"}}, {"title": 1}
        ).limit(limit)
        return [doc["title"] async for doc in cursor]
