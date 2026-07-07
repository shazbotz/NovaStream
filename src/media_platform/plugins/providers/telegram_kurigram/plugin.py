"""Registers the 'kurigram' TelegramGateway adapter.

Requires the `telegram` extra (`pip install -e ".[telegram]"`) - a
missing dependency is caught by plugin discovery as a warning, not a
crash. See provider.py's docstring for this adapter's verification status
(written carefully, not executed).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from media_platform.domain.errors import ConfigurationError
from media_platform.plugins.providers.telegram_kurigram.provider import (
    KurigramTelegramGateway,
)

if TYPE_CHECKING:
    from media_platform.kernel.plugin import ProviderContext


class TelegramKurigramProviderPlugin:
    name = "provider.telegram.kurigram"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "ProviderContext") -> None:
        def build() -> KurigramTelegramGateway:
            missing = [
                var
                for var, value in (
                    ("BOT_TOKEN", ctx.config.bot_token),
                    ("API_ID", ctx.config.api_id),
                    ("API_HASH", ctx.config.api_hash),
                )
                if not value
            ]
            if missing:
                raise ConfigurationError(
                    f"TELEGRAM_PROVIDER=kurigram requires {', '.join(missing)} to be set"
                )
            assert ctx.config.bot_token and ctx.config.api_id and ctx.config.api_hash
            return KurigramTelegramGateway(
                bot_token=ctx.config.bot_token,
                api_id=ctx.config.api_id,
                api_hash=ctx.config.api_hash,
                commands=ctx.commands,
                callbacks=ctx.callbacks,
            )

        ctx.providers.register("telegram", "kurigram", build)


PLUGIN = TelegramKurigramProviderPlugin()
