"""In-memory DatabaseProvider - a fully functional, dependency-free
adapter for local development, tests, and this bootstrap phase.

Not a production data store: nothing here persists across a process
restart, and `query()` is a linear scan. A MongoDatabaseProvider or
PostgresDatabaseProvider (Phase 3) implements the exact same
DatabaseProvider/Repository interface - see docs/architecture/storage.md.
"""

from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

from media_platform.domain.models import QueryFilter

T = TypeVar("T")

# Most entities key themselves by an `id` attribute. A few (FeatureFlag)
# key by a different field - declared here rather than forcing every
# domain model to have an `id` attribute just to satisfy this adapter.
_KEY_FUNCS: dict[str, Callable[[Any], str]] = {
    "feature_flags": lambda flag: flag.name,
}


def _matches(entity_value: Any, criterion_value: Any) -> bool:
    """Mirrors MongoDB's native behavior of `{"field": value}` matching a
    document where `field` is an array containing `value` - needed so
    in-memory-backed queries (e.g. genre browsing's `{"genres": "Action"}`)
    behave the same way regardless of which DatabaseProvider is active.
    """
    if isinstance(entity_value, (list, tuple)):
        return criterion_value in entity_value
    return entity_value == criterion_value


class InMemoryRepository(Generic[T]):
    def __init__(self, key_fn: Callable[[T], str]) -> None:
        self._key_fn = key_fn
        self._data: dict[str, T] = {}

    async def get(self, id: str) -> T | None:
        return self._data.get(id)

    async def save(self, entity: T) -> None:
        self._data[self._key_fn(entity)] = entity

    async def delete(self, id: str) -> None:
        self._data.pop(id, None)

    async def query(self, query_filter: QueryFilter) -> list[T]:
        matches = [
            entity
            for entity in self._data.values()
            if all(_matches(getattr(entity, field, None), value) for field, value in query_filter.criteria.items())
        ]
        end = query_filter.offset + query_filter.limit
        return matches[query_filter.offset : end]


class InMemoryDatabaseProvider:
    def __init__(self) -> None:
        self._repositories: dict[str, InMemoryRepository[Any]] = {}
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    def repository(self, name: str) -> InMemoryRepository[Any]:
        if name not in self._repositories:
            key_fn = _KEY_FUNCS.get(name, lambda entity: getattr(entity, "id"))
            self._repositories[name] = InMemoryRepository(key_fn=key_fn)
        return self._repositories[name]
