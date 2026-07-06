"""Mongo-backed DatabaseProvider and Repository, using motor (the async
MongoDB driver).

NOTE on verification: this file could not be executed against a live
MongoDB instance or even import-checked with `motor` installed in the
environment this was written in (no network access to `pip install
motor`). The codec functions it depends on (codecs.py) are fully unit
tested without a live database. The `motor`/pymongo API calls below
(`find_one`, `replace_one` with `upsert=True`, `delete_one`,
`find().skip().limit()`, async cursor iteration, `create_index`) are
standard, stable, well-documented APIs, written carefully - but treat
this adapter as reviewed-but-not-yet-integration-tested until it's run
against a real MongoDB instance (see tests/integration/README.md).
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

# Imported at module level, deliberately: this is what lets
# `kernel/plugin_manager.py`'s plugin discovery catch "motor isn't
# installed" as a missing-dependency warning at startup (see its handling
# of ModuleNotFoundError), rather than the failure surfacing later and
# less clearly, inside `connect()`, only once this provider is selected.
import motor.motor_asyncio

from media_platform.domain.models import QueryFilter
from media_platform.plugins.providers._mongo_shared.codecs import CODECS, Codec

T = TypeVar("T")


class MongoRepository(Generic[T]):
    def __init__(self, collection: Any, codec: Codec[T]) -> None:
        self._collection = collection
        self._codec = codec

    async def get(self, id: str) -> T | None:
        doc = await self._collection.find_one({"_id": id})
        return self._codec.from_doc(doc) if doc is not None else None

    async def save(self, entity: T) -> None:
        doc = self._codec.to_doc(entity)
        await self._collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)

    async def delete(self, id: str) -> None:
        await self._collection.delete_one({"_id": id})

    async def query(self, query_filter: QueryFilter) -> list[T]:
        cursor = (
            self._collection.find(query_filter.criteria)
            .skip(query_filter.offset)
            .limit(query_filter.limit)
        )
        return [self._codec.from_doc(doc) async for doc in cursor]


class MongoDatabaseProvider:
    """Owns the Mongo connection lifecycle and hands out named
    repositories - one per entry in `codecs.CODECS`.

    Also ensures the text index that `search_mongo_text`'s SearchProvider
    adapter relies on exists (idempotent - `create_index` is a no-op if
    the index is already there), since both adapters operate on the same
    underlying `media` collection by design (see
    docs/architecture/search.md for why search and persistence are
    separate ports that happen to share a backend in this Phase 3
    default, without being required to).
    """

    def __init__(self, url: str, db_name: str = "media_platform") -> None:
        self._url = url
        self._db_name = db_name
        self._client: Any = None
        self._db: Any = None
        self._repositories: dict[str, MongoRepository[Any]] = {}

    async def connect(self) -> None:
        self._client = motor.motor_asyncio.AsyncIOMotorClient(self._url)
        self._db = self._client[self._db_name]
        await self._db["media"].create_index(
            [("file_name", "text"), ("caption", "text")], name="media_text_search"
        )

    async def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()

    def repository(self, name: str) -> MongoRepository[Any]:
        if name not in self._repositories:
            try:
                codec = CODECS[name]
            except KeyError as exc:
                raise KeyError(
                    f"No Mongo codec registered for collection '{name}'. "
                    f"Known collections: {sorted(CODECS)}"
                ) from exc
            self._repositories[name] = MongoRepository(self._db[name], codec)
        return self._repositories[name]
