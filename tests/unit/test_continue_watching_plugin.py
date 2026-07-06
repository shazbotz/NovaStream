"""Unit tests for the continue_watching feature plugin."""

import pytest

from media_platform.domain.errors import AuthenticationError, ValidationError
from media_platform.domain.models import AuthenticatedPrincipal
from media_platform.kernel.api_router import ApiRequest
from media_platform.plugins.features.continue_watching.plugin import ContinueWatchingPlugin
from media_platform.plugins.providers.database_memory.provider import InMemoryDatabaseProvider
from media_platform.services.history_service import HistoryService


class _FakeAuthProvider:
    """Authenticates as a fixed user_id, or nobody, for testing."""

    def __init__(self, user_id: int | None):
        self._user_id = user_id

    async def authenticate(self, credentials):
        if self._user_id is None:
            return None
        return AuthenticatedPrincipal(user_id=self._user_id)


def _make_plugin(user_id: int | None = 42):
    db = InMemoryDatabaseProvider()
    history = HistoryService(repository=db.repository("watch_progress"))
    plugin = ContinueWatchingPlugin()
    plugin._history = history
    plugin._auth = _FakeAuthProvider(user_id)
    return plugin, history


AUTH_HEADERS = {"Authorization": "Bearer test"}


async def test_continue_watching_requires_authentication():
    plugin, _ = _make_plugin(user_id=None)
    with pytest.raises(AuthenticationError):
        await plugin.api_continue_watching(ApiRequest(headers={}))


async def test_record_progress_requires_authentication():
    plugin, _ = _make_plugin(user_id=None)
    with pytest.raises(AuthenticationError):
        await plugin.api_record_progress(
            ApiRequest(headers={}, body={"media_id": "abc", "position_seconds": 10})
        )


async def test_record_then_list_round_trip():
    plugin, _ = _make_plugin(user_id=42)
    await plugin.api_record_progress(
        ApiRequest(
            headers=AUTH_HEADERS,
            body={"media_id": "abc", "position_seconds": 120, "duration_seconds": 5400},
        )
    )

    response = await plugin.api_continue_watching(ApiRequest(headers=AUTH_HEADERS))
    assert response.body["items"] == [
        {"media_id": "abc", "position_seconds": 120, "duration_seconds": 5400}
    ]


async def test_user_id_comes_from_the_authenticated_principal_not_the_client():
    """Security-critical: a client must not be able to read or write
    another user's watch history by passing a different user_id anywhere
    - there's no `user_id` field accepted in the request body/query at
    all, specifically to make this impossible rather than just
    discouraged."""
    plugin_a, history = _make_plugin(user_id=1)
    await plugin_a.api_record_progress(
        ApiRequest(headers=AUTH_HEADERS, body={"media_id": "abc", "position_seconds": 50})
    )

    # A different authenticated user must not see user 1's history.
    plugin_b = ContinueWatchingPlugin()
    plugin_b._history = history
    plugin_b._auth = _FakeAuthProvider(user_id=2)
    response = await plugin_b.api_continue_watching(ApiRequest(headers=AUTH_HEADERS))
    assert response.body["items"] == []


async def test_record_progress_requires_media_id():
    plugin, _ = _make_plugin()
    with pytest.raises(ValidationError):
        await plugin.api_record_progress(
            ApiRequest(headers=AUTH_HEADERS, body={"position_seconds": 10})
        )


async def test_record_progress_rejects_negative_position():
    plugin, _ = _make_plugin()
    with pytest.raises(ValidationError):
        await plugin.api_record_progress(
            ApiRequest(headers=AUTH_HEADERS, body={"media_id": "abc", "position_seconds": -1})
        )


async def test_record_progress_rejects_non_integer_position():
    plugin, _ = _make_plugin()
    with pytest.raises(ValidationError):
        await plugin.api_record_progress(
            ApiRequest(
                headers=AUTH_HEADERS, body={"media_id": "abc", "position_seconds": "not-a-number"}
            )
        )


async def test_record_progress_defaults_duration_to_zero():
    plugin, _ = _make_plugin()
    await plugin.api_record_progress(
        ApiRequest(headers=AUTH_HEADERS, body={"media_id": "abc", "position_seconds": 5})
    )
    response = await plugin.api_continue_watching(ApiRequest(headers=AUTH_HEADERS))
    assert response.body["items"][0]["duration_seconds"] == 0
