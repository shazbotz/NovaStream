"""Registers the 'telegram' StorageProvider adapter.

Requires the `telegram` extra (`pip install -e ".[telegram]"`), same as
`telegram_kurigram` - a missing dependency is only discovered when the
adapter is actually used (see `client.py`'s lazy import), not at plugin
discovery time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from media_platform.domain.errors import ConfigurationError
from media_platform.plugins.providers.storage_telegram.client import TelegramStreamClientPool
from media_platform.plugins.providers.storage_telegram.provider import TelegramStorageProvider

if TYPE_CHECKING:
    from media_platform.kernel.plugin import ProviderContext


class StorageTelegramProviderPlugin:
    name = "provider.storage.telegram"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "ProviderContext") -> None:
        def build() -> TelegramStorageProvider:
            missing = [
                var
                for var, value in (
                    ("API_ID", ctx.config.api_id),
                    ("API_HASH", ctx.config.api_hash),
                )
                if not value
            ]
            if missing:
                raise ConfigurationError(
                    f"STORAGE_PROVIDER=telegram requires {', '.join(missing)} to be set"
                )
            # Falls back to the single BOT_TOKEN used for the bot-core
            # gateway when no dedicated STREAM_WORKER_TOKENS are
            # configured - see client.py's docstring on why a
            # single-token pool is a config state, not a special case.
            tokens = ctx.config.stream_worker_tokens or (
                (ctx.config.bot_token,) if ctx.config.bot_token else ()
            )
            if not tokens:
                raise ConfigurationError(
                    "STORAGE_PROVIDER=telegram requires BOT_TOKEN or STREAM_WORKER_TOKENS "
                    "to be set"
                )
            assert ctx.config.api_id and ctx.config.api_hash
            pool = TelegramStreamClientPool(
                api_id=ctx.config.api_id,
                api_hash=ctx.config.api_hash,
                bot_tokens=tokens,
            )
            return TelegramStorageProvider(pool=pool, chunk_size=ctx.config.stream_chunk_size)

        ctx.providers.register("storage", "telegram", build)


PLUGIN = StorageTelegramProviderPlugin()
