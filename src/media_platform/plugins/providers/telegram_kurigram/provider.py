"""kurigram (Pyrogram-compatible)-backed TelegramGateway.

Covers both `TelegramGateway`'s outbound surface (checking membership,
reading messages, sending messages) and inbound update dispatch: incoming
`/command` messages are routed through the shared `CommandRegistry`, and
incoming callback queries through the shared `CallbackRegistry`, so every
feature plugin's `ctx.commands.register(...)` / `ctx.callbacks.register(...)`
call actually reaches a live Telegram chat.

kurigram is a Pyrogram-API-compatible fork distributed so that existing
`import pyrogram` code keeps working unchanged - this file follows that
same convention. If the installed `kurigram` package does *not* expose
itself under the `pyrogram` import name in the version you install,
update the import at the top of this file accordingly; verify against
whatever version you pin in `pyproject.toml`'s `telegram` extra.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant
from pyrogram.handlers import CallbackQueryHandler, MessageHandler

from media_platform.domain.models import MemberStatus

if TYPE_CHECKING:
    from media_platform.kernel.callback_registry import CallbackRegistry
    from media_platform.kernel.command_registry import CommandRegistry

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
        commands: "CommandRegistry",
        callbacks: "CallbackRegistry",
        session_name: str = "media_platform_bot",
    ) -> None:
        self._commands = commands
        self._callbacks = callbacks
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
        # Registered here (constructor time) rather than after `connect()`
        # so the dispatcher is guaranteed to exist before `client.start()`
        # begins receiving updates. Deliberately NOT using
        # `filters.command([...])` with a fixed command list: at this
        # point in startup (Pass 1 - providers), feature plugins (Pass 2)
        # haven't registered their commands into `self._commands` yet, so
        # any list captured here would be stale. Instead every text
        # message is routed to `_on_message`, which resolves the command
        # against the registry at call time - by then (a real user
        # sending a message, well after startup finishes) the registry is
        # fully populated regardless of Pass 1/Pass 2 ordering.
        self._client.add_handler(MessageHandler(self._on_message, filters=_command_filter()))
        self._client.add_handler(CallbackQueryHandler(self._on_callback_query))

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

    # --- inbound update dispatch -----------------------------------------

    async def _on_message(self, _client: Client, message: Any) -> None:
        text: str | None = getattr(message, "text", None) or getattr(message, "caption", None)
        if not text or not text.startswith("/"):
            return

        head, _, rest = text.strip().partition(" ")
        command = head[1:].split("@", 1)[0].lower()  # strip leading "/" and "@botname"
        args = rest.strip()

        if command == "start":
            available = ", ".join(f"/{name}" for name in self._commands.all_commands())
            greeting = "Welcome to Nova Stream!"
            await message.reply_text(
                f"{greeting} Available commands: {available}" if available else
                f"{greeting} No commands are available yet."
            )
            return

        handler = self._commands.get(command)
        if handler is None:
            logger.info("Received unknown command '/%s'", command)
            await message.reply_text(f"Unknown command: /{command}")
            return

        try:
            await handler(args=args, reply=message.reply_text)
        except Exception:
            logger.exception("Command handler for '/%s' raised", command)
            await message.reply_text("Something went wrong handling that command.")

    async def _on_callback_query(self, _client: Client, callback_query: Any) -> None:
        data: str | None = getattr(callback_query, "data", None)
        if not data:
            return

        handler = self._callbacks.resolve(data)
        if handler is None:
            logger.info("Received unroutable callback_query data '%s'", data)
            await callback_query.answer("This action is no longer available.")
            return

        try:
            await handler(callback_query)
        except Exception:
            logger.exception("Callback handler for '%s' raised", data)
            await callback_query.answer("Something went wrong handling that action.")


def _command_filter() -> Any:
    """Matches any text/caption message - see `_on_message`'s docstring
    comment for why this doesn't use `filters.command([...])` with a
    fixed list.
    """
    from pyrogram import filters

    return filters.text | filters.caption
