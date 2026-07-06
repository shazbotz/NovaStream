"""kurigram (Pyrogram-compatible)-backed TelegramGateway.

**This is the least verified file in this project.** Unlike the Mongo
adapters (motor's API is small and stable, and the pure-function codec
logic is fully unit tested), this file could not be checked in any way
beyond `py_compile` syntax validation: `kurigram` isn't installed in the
environment this was written in (no network access to install it), and
even with it installed, exercising this adapter for real needs a live
bot token, api_id, and api_hash, plus a real Telegram chat to call
against. Nothing here has been run.

kurigram is a Pyrogram-API-compatible fork distributed so that existing
`import pyrogram` code keeps working unchanged - this file follows that
same convention. If the installed `kurigram` package does *not* expose
itself under the `pyrogram` import name in the version you install,
update the import at the top of this file accordingly; verify against
whatever version you pin in `pyproject.toml`'s `telegram` extra.

Deliberately NOT implemented here: receiving/dispatching *inbound*
updates (turning an incoming Telegram message into a
`CommandRegistry`/`CallbackRegistry` call). This adapter only covers
`TelegramGateway`'s outbound surface (checking membership, reading
messages, sending messages). Wiring a live bot polling loop is a
substantial, separate piece of work that deserves its own focused,
testable pass with a real bot token available - see ROADMAP.md.
"""

from __future__ import annotations

import logging
from typing import Any

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant

from media_platform.domain.models import MemberStatus

logger = logging.getLogger(__name__)

_STATUS_MAP: dict[Any, MemberStatus] = {
    ChatMemberStatus.OWNER: MemberStatus.OWNER,
    ChatMemberStatus.ADMINISTRATOR: MemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER: MemberStatus.MEMBER,
    ChatMemberStatus.RESTRICTED: MemberStatus.MEMBER,  # still in the chat
    ChatMemberStatus.LEFT: MemberStatus.LEFT,
    ChatMemberStatus.BANNED: MemberStatus.KICKED,
}


class KurigramTelegramGateway:
    def __init__(
        self,
        bot_token: str,
        api_id: int,
        api_hash: str,
        session_name: str = "media_platform_bot",
    ) -> None:
        self._client = Client(
            session_name,
            api_id=api_id,
            api_hash=api_hash,
            bot_token=bot_token,
            in_memory=True,  # no session file on disk - fine for a bot
            # account (unlike a user account, a bot doesn't need a
            # persistent session across restarts to avoid re-login
            # friction); avoids needing writable local storage, which
            # Koyeb's free tier doesn't offer (architecture-design-
            # phase1.md §2: "Persistent volumes: not available").
        )

    async def connect(self) -> None:
        await self._client.start()

    async def disconnect(self) -> None:
        await self._client.stop()

    async def get_chat_member(self, chat_id: int, user_id: int) -> MemberStatus:
        try:
            member = await self._client.get_chat_member(chat_id, user_id)
        except UserNotParticipant:
            return MemberStatus.LEFT
        return _STATUS_MAP.get(member.status, MemberStatus.UNKNOWN)

    async def get_messages(self, chat_id: int, message_ids: list[int]) -> list[Any]:
        return await self._client.get_messages(chat_id, message_ids)

    async def send_message(self, chat_id: int, text: str, **kwargs: Any) -> Any:
        return await self._client.send_message(chat_id, text, **kwargs)
