"""Plugin contracts and the context objects plugins receive.

A plugin never imports aiohttp, a Telegram client library, a database
driver, or any other third-party adapter library directly - everything it
needs is reachable through the context handed to `register()`. See
docs/guides/plugin-development.md.

There are two kinds of plugin, matching the two directories under
`plugins/` (architecture-design-phase1-v3.md §3):

- ``ProviderPlugin`` (plugins/providers/*): registers one adapter
  implementation for a port. Gets a minimal ``ProviderContext`` -
  registration only, no services, since services are what get built FROM
  the providers once they're all registered.
- ``FeaturePlugin`` (plugins/features/*): registers commands, callbacks,
  routes, jobs, settings, and models. Gets the full ``PluginContext``,
  including the already-constructed core services.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from media_platform.config import Settings
from media_platform.kernel.api_router import ApiRouter
from media_platform.kernel.callback_registry import CallbackRegistry
from media_platform.kernel.command_registry import CommandRegistry
from media_platform.kernel.model_registry import ModelRegistry
from media_platform.kernel.provider_registry import ProviderRegistry
from media_platform.kernel.scheduler import Scheduler
from media_platform.kernel.service_locator import ServiceLocator
from media_platform.kernel.settings_registry import SettingsRegistry


@dataclass(frozen=True)
class ProviderContext:
    """``config`` is the raw application Settings - the one deliberate
    exception to "plugins never read os.environ directly". Provider
    plugins are infrastructure adapters; they legitimately need
    connection strings/credentials (``config.database_url``,
    ``config.bot_token``, ...) to construct a real client. Feature
    plugins do NOT get this - they declare configurable settings through
    ``ctx.settings`` (SettingsRegistry) instead. Named ``config`` rather
    than ``settings`` specifically to avoid confusion with
    ``PluginContext.settings`` below, which is a different thing.
    """

    providers: ProviderRegistry
    config: Settings
    commands: CommandRegistry
    callbacks: CallbackRegistry


@dataclass(frozen=True)
class PluginContext:
    providers: ProviderRegistry
    commands: CommandRegistry
    callbacks: CallbackRegistry
    api: ApiRouter
    scheduler: Scheduler
    settings: SettingsRegistry
    models: ModelRegistry
    services: ServiceLocator


@runtime_checkable
class ProviderPlugin(Protocol):
    name: str
    version: str
    requires: tuple[str, ...]

    def register(self, ctx: ProviderContext) -> None: ...


@runtime_checkable
class FeaturePlugin(Protocol):
    name: str
    version: str
    requires: tuple[str, ...]

    def register(self, ctx: PluginContext) -> None: ...
