"""Read-only bundle of core services handed to feature plugins via
`PluginContext.services`.

Plugins call these, never a concrete adapter directly. Bot command
handlers and HTTP API route handlers both call the same services here -
see architecture-design-phase1-v3.md §4 (API-first rule) - so logic is
never duplicated between transports.
"""

from __future__ import annotations

from dataclasses import dataclass

from media_platform.cache.ttl_cache import TTLCache
from media_platform.domain.interfaces import AuthProvider, FeatureFlags, TelegramGateway
from media_platform.services.catalog_service import CatalogService
from media_platform.services.history_service import HistoryService
from media_platform.services.playback_service import PlaybackService


@dataclass(frozen=True)
class ServiceLocator:
    catalog: CatalogService
    playback: PlaybackService
    history: HistoryService
    flags: FeatureFlags
    telegram: TelegramGateway
    auth: AuthProvider
    cache: TTLCache
