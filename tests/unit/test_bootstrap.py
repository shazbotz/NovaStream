"""End-to-end wiring test for the bootstrap phase.

Exercises the exact sequence `server.build_application()` follows (minus
the aiohttp-specific parts, which are integration-tested separately): load
provider plugins, resolve every port, build services, load feature
plugins, and confirm the null adapters fail loudly rather than silently
when their (not-yet-implemented) real work is requested.

If this test passes, "the project compiles and starts successfully" is
true for everything except actually binding an HTTP socket.
"""

import pytest

from media_platform.cache.ttl_cache import TTLCache
from media_platform.config import Settings
from media_platform.domain.errors import ProviderError
from media_platform.domain.models import CatalogItem, SearchQuery, StorageRef
from media_platform.kernel.api_router import ApiRouter
from media_platform.kernel.callback_registry import CallbackRegistry
from media_platform.kernel.command_registry import CommandRegistry
from media_platform.kernel.model_registry import ModelRegistry
from media_platform.kernel.plugin import PluginContext, ProviderContext
from media_platform.kernel.plugin_manager import (
    FEATURE_PACKAGE,
    PROVIDER_PACKAGE,
    PluginManager,
)
from media_platform.kernel.provider_registry import ProviderRegistry
from media_platform.kernel.scheduler import Scheduler
from media_platform.kernel.service_locator import ServiceLocator
from media_platform.kernel.settings_registry import SettingsRegistry
from media_platform.services.catalog_service import CatalogService
from media_platform.services.feature_flags import FeatureFlagService
from media_platform.services.history_service import HistoryService
from media_platform.services.playback_service import PlaybackService


@pytest.fixture
def settings(monkeypatch):
    # Bootstrap defaults (null/memory adapters) require no environment
    # variables at all - this confirms that stays true.
    for var in list(Settings.load().__dict__):
        monkeypatch.delenv(var.upper(), raising=False)
    return Settings.load()


async def test_full_bootstrap_wiring(settings):
    registry = ProviderRegistry()
    manager = PluginManager()

    provider_ctx = ProviderContext(providers=registry, config=settings)
    manager.load_package(PROVIDER_PACKAGE, provider_ctx)
    # 9 = the 6 original bootstrap-phase adapters + this pass's
    # `streaming_signed` and `storage_telegram` + the pre-existing
    # `streaming_null` (there was no dedicated streaming adapter to count
    # before this pass added a second one to choose between).
    assert len(manager.loaded_plugin_names()) == 9
    assert "provider.streaming.signed" in manager.loaded_plugin_names()
    assert "provider.storage.telegram" in manager.loaded_plugin_names()

    search = registry.get("search", settings.search_provider)
    storage = registry.get("storage", settings.storage_provider)
    database = registry.get("database", settings.database_provider)
    auth = registry.get("auth", settings.auth_provider)
    metadata = registry.get("metadata", settings.metadata_provider)
    streaming = registry.get("streaming", settings.streaming_provider)
    telegram = registry.get("telegram", settings.telegram_provider)

    await database.connect()
    await telegram.connect()

    cache: TTLCache = TTLCache(max_size=settings.cache_max_size, ttl_seconds=settings.cache_ttl_seconds)
    flags = FeatureFlagService(repository=database.repository("feature_flags"), cache=cache)
    catalog = CatalogService(repository=database.repository("media"), search=search)
    playback = PlaybackService(streaming=streaming)
    history = HistoryService(repository=database.repository("watch_progress"))
    services = ServiceLocator(catalog=catalog, playback=playback, history=history,
                               flags=flags, telegram=telegram, auth=auth, cache=cache)

    feature_ctx = PluginContext(
        providers=registry, commands=CommandRegistry(), callbacks=CallbackRegistry(),
        api=ApiRouter(), scheduler=Scheduler(), settings=SettingsRegistry(),
        models=ModelRegistry(), services=services,
    )
    # Must not raise - and now that catalog_search exists, must actually
    # register its command and API route (this is what proves plugin
    # discovery + the two-pass loading sequence works end to end for a
    # real feature, not just for zero plugins).
    manager.load_package(FEATURE_PACKAGE, feature_ctx)
    assert "feature.catalog_search" in manager.loaded_plugin_names()
    assert feature_ctx.commands.get("search") is not None
    assert any(route.path == "/api/search" for route in feature_ctx.api.routes())

    item = CatalogItem(
        id="abc", title="Sample", file_name="sample.mkv", file_size=1,
        mime_type="video/mp4",
        storage_ref=StorageRef(provider="telegram", payload={}),
    )
    await catalog.index_item(item)
    assert (await catalog.get_item("abc")).title == "Sample"
    assert (await catalog.search(SearchQuery.from_text("sample"))).total == 0

    with pytest.raises(ProviderError):
        await playback.request_playback("abc", user_id=1)

    assert auth is not None
    assert metadata is not None
    assert telegram is not None
    assert storage is not None
