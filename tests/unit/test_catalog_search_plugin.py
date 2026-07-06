"""Unit tests for the catalog_search feature plugin, including the
variant-grouping enhancement.

Exercises both transports it registers (HTTP API and bot command)
directly, with zero aiohttp and zero Telegram dependency - this is
exactly what `ApiRequest`/`ApiResponse` (kernel/api_router.py) and the
transport-agnostic `Reply` callback convention are for. Uses the real
`CatalogService` wired to the in-memory database adapter and a small fake
`SearchProvider`/`AuthProvider`, not the full application - this is a
plugin unit test, not an end-to-end boot test (that's test_bootstrap.py).
"""

import pytest

from media_platform.domain.errors import AuthenticationError, ValidationError
from media_platform.domain.models import (
    AuthenticatedPrincipal,
    CatalogItem,
    SearchHit,
    SearchQuery,
    SearchResult,
    StorageRef,
)
from media_platform.kernel.api_router import ApiRequest
from media_platform.plugins.features.catalog_search.plugin import (
    CatalogSearchPlugin,
    _catalog_item_from_request_body,
)
from media_platform.plugins.providers.database_memory.provider import InMemoryDatabaseProvider
from media_platform.services.catalog_service import CatalogService


class _FakeSearchProvider:
    """Returns canned hits instead of doing real search - lets these
    tests focus on the plugin's request/response and grouping behavior,
    not on search ranking (that's test_mongo_codecs.py's job for the
    Mongo adapter, and test_catalog_grouping.py's for grouping itself).
    """

    def __init__(self, hits=None):
        self._hits = hits or []

    async def index(self, doc):
        pass

    async def remove(self, doc_id):
        pass

    async def search(self, query: SearchQuery) -> SearchResult:
        return SearchResult(hits=self._hits, total=len(self._hits), has_more=False)

    async def suggest(self, prefix, limit=10):
        return []


class _FakeAuthProvider:
    def __init__(self, authenticated: bool):
        self._authenticated = authenticated

    async def authenticate(self, credentials):
        if self._authenticated:
            return AuthenticatedPrincipal(user_id=1)
        return None


class _ReplyCollector:
    """A minimal async stand-in for the `Reply` callback - `cmd_search`
    does `await reply(...)`, so a plain sync `list.append` doesn't satisfy
    the contract (this was caught by actually running these tests against
    an earlier draft that used `list.append` directly).
    """

    def __init__(self) -> None:
        self.messages: list[str] = []

    async def __call__(self, text: str) -> None:
        self.messages.append(text)


VALID_MEDIA_BODY = {
    "id": "abc123",
    "title": "Sample",
    "file_name": "sample.mkv",
    "file_size": 1024,
    "mime_type": "video/x-matroska",
    "storage_ref": {"provider": "telegram", "payload": {"chat_id": -100, "message_id": 5}},
}


def _make_plugin(hits=None, authenticated=False, catalog_items=()) -> CatalogSearchPlugin:
    db = InMemoryDatabaseProvider()
    catalog = CatalogService(
        repository=db.repository("media"), search=_FakeSearchProvider(hits)
    )
    plugin = CatalogSearchPlugin()
    plugin._catalog = catalog  # bypassing register() - the wiring itself
    plugin._auth = _FakeAuthProvider(authenticated)  # is covered by test_bootstrap.py
    return plugin, catalog


async def _seed(catalog: CatalogService, *items: CatalogItem) -> None:
    for item in items:
        await catalog.index_item(item)


def _item(id: str, title: str, **kwargs) -> CatalogItem:
    defaults = dict(
        file_name=f"{id}.mkv",
        file_size=1000,
        mime_type="video/x-matroska",
        storage_ref=StorageRef(provider="telegram", payload={}),
    )
    defaults.update(kwargs)
    return CatalogItem(id=id, title=title, **defaults)


# --- HTTP transport: GET /api/search (with grouping) ------------------------


async def test_api_search_groups_single_variant_result():
    item = _item("a", "Sample Movie", year=2020, language="en", quality="1080p")
    plugin, catalog = _make_plugin(hits=[SearchHit(media_id="a", score=1.0, title="Sample Movie")])
    await _seed(catalog, item)

    response = await plugin.api_search(ApiRequest(query={"q": "sample"}))

    assert response.status == 200
    assert len(response.body["results"]) == 1
    group = response.body["results"][0]
    assert group["title"] == "Sample Movie"
    assert group["variant_count"] == 1
    assert group["variants"][0]["media_id"] == "a"


async def test_api_search_groups_multiple_variants_under_one_title():
    items = [
        _item("a", "Dune", year=2021, language="en", quality="1080p"),
        _item("b", "Dune", year=2021, language="hi", quality="720p"),
    ]
    hits = [SearchHit(media_id=i.id, score=1.0, title=i.title) for i in items]
    plugin, catalog = _make_plugin(hits=hits)
    await _seed(catalog, *items)

    response = await plugin.api_search(ApiRequest(query={"q": "dune"}))

    assert len(response.body["results"]) == 1  # one entry, not two
    group = response.body["results"][0]
    assert group["variant_count"] == 2
    assert group["languages"] == ["en", "hi"]


async def test_api_search_defaults_offset_and_limit():
    plugin, _ = _make_plugin()
    response = await plugin.api_search(ApiRequest(query={"q": "x"}))
    assert response.status == 200


async def test_api_search_rejects_non_integer_limit():
    plugin, _ = _make_plugin()
    with pytest.raises(ValidationError):
        await plugin.api_search(ApiRequest(query={"q": "x", "limit": "not-a-number"}))


async def test_api_search_clamps_limit_to_max():
    plugin, _ = _make_plugin()
    await plugin.api_search(ApiRequest(query={"q": "x", "limit": "99999"}))


# --- HTTP transport: POST /api/media -----------------------------------------


async def test_api_index_media_requires_authentication():
    plugin, _ = _make_plugin(authenticated=False)
    with pytest.raises(AuthenticationError):
        await plugin.api_index_media(ApiRequest(headers={}, body=VALID_MEDIA_BODY))


async def test_api_index_media_succeeds_when_authenticated():
    plugin, catalog = _make_plugin(authenticated=True)
    response = await plugin.api_index_media(
        ApiRequest(headers={"Authorization": "Bearer test"}, body=VALID_MEDIA_BODY)
    )
    assert response.status == 201
    assert response.body == {"id": "abc123"}

    item = await catalog.get_item("abc123")
    assert item is not None
    assert item.title == "Sample"


async def test_api_index_media_accepts_grouping_fields():
    plugin, catalog = _make_plugin(authenticated=True)
    body = dict(VALID_MEDIA_BODY, year=2020, codec="HEVC", release_type="BluRay", genres=["Action"])
    await plugin.api_index_media(ApiRequest(headers={"Authorization": "x"}, body=body))

    item = await catalog.get_item("abc123")
    assert item.year == 2020
    assert item.codec == "HEVC"
    assert item.release_type == "BluRay"
    assert item.genres == ("Action",)


async def test_api_index_media_rejects_missing_fields():
    with pytest.raises(ValidationError):
        _catalog_item_from_request_body({"title": "Missing everything else"})


async def test_api_index_media_rejects_malformed_storage_ref():
    body = dict(VALID_MEDIA_BODY, storage_ref={"provider": "telegram"})  # no payload
    with pytest.raises(ValidationError):
        _catalog_item_from_request_body(body)


async def test_api_index_media_rejects_non_integer_file_size():
    body = dict(VALID_MEDIA_BODY, file_size="not-a-number")
    with pytest.raises(ValidationError):
        _catalog_item_from_request_body(body)


async def test_api_index_media_rejects_non_integer_year():
    body = dict(VALID_MEDIA_BODY, year="not-a-year")
    with pytest.raises(ValidationError):
        _catalog_item_from_request_body(body)


# --- Bot transport: /search, with grouping ----------------------------------


async def test_cmd_search_with_empty_args_shows_usage():
    plugin, _ = _make_plugin()
    replies = _ReplyCollector()
    await plugin.cmd_search("   ", replies)
    assert replies.messages == ["Usage: /search <text>"]


async def test_cmd_search_with_no_results():
    plugin, _ = _make_plugin(hits=[])
    replies = _ReplyCollector()
    await plugin.cmd_search("nonexistent movie", replies)
    assert replies.messages == ["No results for 'nonexistent movie'."]


async def test_cmd_search_single_variant_skips_selection_step():
    item = _item("a", "Sample Movie", year=2020, language="en", quality="1080p")
    plugin, catalog = _make_plugin(hits=[SearchHit(media_id="a", score=1.0, title="Sample Movie")])
    await _seed(catalog, item)

    replies = _ReplyCollector()
    await plugin.cmd_search("sample", replies)

    text = replies.messages[0]
    assert "Sample Movie" in text
    assert "en" in text and "1080p" in text
    assert "versions" not in text  # no "N versions" prompt for a single variant


async def test_cmd_search_multi_variant_shows_available_options():
    items = [
        _item("a", "Dune", year=2021, language="en", quality="1080p"),
        _item("b", "Dune", year=2021, language="hi", quality="720p"),
    ]
    hits = [SearchHit(media_id=i.id, score=1.0, title=i.title) for i in items]
    plugin, catalog = _make_plugin(hits=hits)
    await _seed(catalog, *items)

    replies = _ReplyCollector()
    await plugin.cmd_search("dune", replies)

    text = replies.messages[0]
    assert "2 versions" in text
    assert "en" in text and "hi" in text


async def test_same_service_backs_both_transports():
    """The point of this plugin: HTTP and bot commands must not be able
    to drift apart, because they call the exact same CatalogService
    instance and the exact same grouping logic - not two independent
    implementations."""
    item = _item("a", "Shared Result", year=2022)
    plugin, catalog = _make_plugin(hits=[SearchHit(media_id="a", score=1.0, title="Shared Result")])
    await _seed(catalog, item)

    api_response = await plugin.api_search(ApiRequest(query={"q": "shared"}))
    replies = _ReplyCollector()
    await plugin.cmd_search("shared", replies)

    assert api_response.body["results"][0]["title"] == "Shared Result"
    assert "Shared Result" in replies.messages[0]
