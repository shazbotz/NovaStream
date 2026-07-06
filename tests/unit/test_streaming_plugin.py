"""Unit tests for the streaming feature plugin.

Uses the in-memory database provider (already used by the other feature
plugin tests) plus a fake `StreamingService` so this exercises the
plugin's HTTP-facing behavior (auth, validation, 404s, dl-tagging)
without needing STREAM_SECRET, a real HMAC, or any Telegram/storage
adapter.
"""

import pytest

from media_platform.domain.errors import AuthenticationError, NotFoundError, ValidationError
from media_platform.domain.models import (
    AuthenticatedPrincipal,
    CatalogItem,
    PlaybackURL,
    StorageRef,
    utcnow,
)
from media_platform.kernel.api_router import ApiRequest
from media_platform.plugins.features.streaming.plugin import StreamingPlugin
from media_platform.plugins.providers.database_memory.provider import InMemoryDatabaseProvider
from media_platform.services.catalog_service import CatalogService
from media_platform.services.playback_service import PlaybackService


class _FakeAuthProvider:
    def __init__(self, user_id: int | None):
        self._user_id = user_id

    async def authenticate(self, credentials):
        if self._user_id is None:
            return None
        return AuthenticatedPrincipal(user_id=self._user_id)


class _FakeSearchProvider:
    async def index(self, doc):
        pass

    async def remove(self, doc_id):
        pass

    async def search(self, query):
        raise NotImplementedError

    async def suggest(self, prefix, limit=10):
        return []


class _FakeStreamingService:
    async def get_playback_url(self, media_id, user_id, *, expiry_seconds=21600):
        return PlaybackURL(
            url=f"https://example.test/stream/{media_id}?exp=1&sig=abc&u={user_id}",
            expires_at=utcnow(),
        )

    async def revoke(self, media_id, user_id):
        pass


AUTH_HEADERS = {"Authorization": "Bearer test"}


async def _make_plugin(user_id: int | None = 42, seed_item: CatalogItem | None = None):
    db = InMemoryDatabaseProvider()
    catalog = CatalogService(repository=db.repository("media"), search=_FakeSearchProvider())
    if seed_item is not None:
        await db.repository("media").save(seed_item)

    plugin = StreamingPlugin()
    plugin._catalog = catalog
    plugin._playback = PlaybackService(streaming=_FakeStreamingService())
    plugin._auth = _FakeAuthProvider(user_id)
    return plugin


def _item(media_id="movie-1") -> CatalogItem:
    return CatalogItem(
        id=media_id,
        title="Interstellar",
        file_name="interstellar.1080p.mkv",
        file_size=2_200_000_000,
        mime_type="video/x-matroska",
        storage_ref=StorageRef(provider="telegram", payload={"chat_id": -100, "message_id": 5}),
    )


async def test_stream_token_requires_authentication():
    plugin = await _make_plugin(user_id=None, seed_item=_item())
    with pytest.raises(AuthenticationError):
        await plugin.api_stream_token(
            ApiRequest(headers={}, path_params={"media_id": "movie-1"})
        )


async def test_stream_token_requires_media_id():
    plugin = await _make_plugin()
    with pytest.raises(ValidationError):
        await plugin.api_stream_token(ApiRequest(headers=AUTH_HEADERS, path_params={}))


async def test_stream_token_404s_for_unknown_media():
    plugin = await _make_plugin()
    with pytest.raises(NotFoundError):
        await plugin.api_stream_token(
            ApiRequest(headers=AUTH_HEADERS, path_params={"media_id": "does-not-exist"})
        )


async def test_stream_token_returns_playback_url_and_file_info():
    plugin = await _make_plugin(seed_item=_item())
    response = await plugin.api_stream_token(
        ApiRequest(headers=AUTH_HEADERS, path_params={"media_id": "movie-1"})
    )
    assert response.body["file_name"] == "interstellar.1080p.mkv"
    assert response.body["file_size"] == 2_200_000_000
    assert "dl=1" not in response.body["url"]


async def test_download_token_tags_the_url_for_attachment_download():
    plugin = await _make_plugin(seed_item=_item())
    response = await plugin.api_download_token(
        ApiRequest(headers=AUTH_HEADERS, path_params={"media_id": "movie-1"})
    )
    assert response.body["url"].endswith("&dl=1")
