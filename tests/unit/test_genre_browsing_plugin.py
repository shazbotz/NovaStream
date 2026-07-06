"""Unit tests for the genre_browsing feature plugin."""

import pytest

from media_platform.domain.errors import ValidationError
from media_platform.domain.models import CatalogItem, StorageRef
from media_platform.kernel.api_router import ApiRequest
from media_platform.plugins.features.genre_browsing.plugin import GenreBrowsingPlugin
from media_platform.plugins.providers.database_memory.provider import InMemoryDatabaseProvider
from media_platform.services.catalog_service import CatalogService


class _NullSearch:
    async def index(self, doc):
        pass

    async def remove(self, doc_id):
        pass

    async def search(self, query):
        raise AssertionError("genre browsing must not go through SearchProvider")

    async def suggest(self, prefix, limit=10):
        return []


def _item(id: str, title: str, genres=()) -> CatalogItem:
    return CatalogItem(
        id=id,
        title=title,
        file_name=f"{id}.mkv",
        file_size=1,
        mime_type="video/mp4",
        storage_ref=StorageRef(provider="telegram", payload={}),
        genres=genres,
    )


async def _make_plugin_with_items(*items: CatalogItem) -> GenreBrowsingPlugin:
    db = InMemoryDatabaseProvider()
    catalog = CatalogService(repository=db.repository("media"), search=_NullSearch())
    for item in items:
        await catalog.index_item(item)

    plugin = GenreBrowsingPlugin()
    plugin._catalog = catalog
    return plugin


async def test_returns_only_items_tagged_with_the_requested_genre():
    plugin = await _make_plugin_with_items(
        _item("a", "Action Movie", genres=("Action", "Thriller")),
        _item("b", "Comedy Movie", genres=("Comedy",)),
    )

    response = await plugin.api_by_genre(ApiRequest(path_params={"genre": "Action"}))

    assert [i["media_id"] for i in response.body["items"]] == ["a"]


async def test_item_with_multiple_genres_shows_up_under_each():
    plugin = await _make_plugin_with_items(
        _item("a", "Action Comedy", genres=("Action", "Comedy")),
    )

    action_response = await plugin.api_by_genre(ApiRequest(path_params={"genre": "Action"}))
    comedy_response = await plugin.api_by_genre(ApiRequest(path_params={"genre": "Comedy"}))

    assert len(action_response.body["items"]) == 1
    assert len(comedy_response.body["items"]) == 1


async def test_unknown_genre_returns_empty_list_not_an_error():
    plugin = await _make_plugin_with_items(_item("a", "Something", genres=("Drama",)))
    response = await plugin.api_by_genre(ApiRequest(path_params={"genre": "Horror"}))
    assert response.body["items"] == []


async def test_missing_genre_path_param_is_rejected():
    plugin = await _make_plugin_with_items()
    with pytest.raises(ValidationError):
        await plugin.api_by_genre(ApiRequest(path_params={}))


async def test_pagination_offset_and_limit_are_respected():
    items = [_item(str(i), f"Movie {i}", genres=("Action",)) for i in range(5)]
    plugin = await _make_plugin_with_items(*items)

    response = await plugin.api_by_genre(
        ApiRequest(path_params={"genre": "Action"}, query={"offset": "2", "limit": "2"})
    )
    assert len(response.body["items"]) == 2
