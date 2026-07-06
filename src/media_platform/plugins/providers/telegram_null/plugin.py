"""Registers the 'null' TelegramGateway adapter - logs and no-ops instead
of calling the real Telegram API. Default until BOT_TOKEN and a real
adapter (kurigram-backed) are configured in Phase 3.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from media_platform.domain.models import MemberStatus

if TYPE_CHECKING:
    from media_platform.kernel.plugin import ProviderContext

logger = logging.getLogger(__name__)


class NullTelegramGateway:
    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def get_chat_member(self, chat_id: int, user_id: int) -> MemberStatus:
        return MemberStatus.UNKNOWN

    async def get_messages(self, chat_id: int, message_ids: list[int]) -> list[Any]:
        return []

    async def send_message(self, chat_id: int, text: str, **kwargs: Any) -> None:
        logger.warning("TelegramGateway not configured; send_message() was a no-op")
        return None


class TelegramNullProviderPlugin:
    name = "provider.telegram.null"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "ProviderContext") -> None:
        ctx.providers.register("telegram", "null", NullTelegramGateway)


PLUGIN = TelegramNullProviderPlugin()
