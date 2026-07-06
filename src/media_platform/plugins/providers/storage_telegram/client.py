"""Telegram SDK wrapper for the streaming worker pool.

**This is the least verified file added in this pass** - same caveat as
`plugins/providers/telegram_kurigram/provider.py`: `kurigram` is not
installed in the environment this was written in (no network access to
install it), and even installed, exercising this against real Telegram
servers needs a live bot token, api_id, api_hash, and a real file to
fetch. Nothing here has been run - only `python -m py_compile`'d.

Deliberately a *separate* client pool from `telegram_kurigram`'s
`KurigramTelegramGateway`, not a reuse of it, matching the worker-pool
design already specified (not yet implemented) in
`docs/design-log/architecture-design-phase1.md` §4.3: "if you have more
than one bot token available, start N Pyrogram/kurigram clients at boot,
round-robin requests across them ... With a single token, the engine
still works, just without the extra fan-out." The bot-core gateway
(`TelegramGateway`, used for membership checks and sending messages) and
this streaming client pool (used for pulling file bytes) are allowed to
be two independent connections to Telegram; nothing in
`domain/interfaces.py` requires them to share a client, and coupling them
would mean a spike in streaming traffic could starve the bot's ability to
answer commands, and vice versa.

Connections are made lazily (on first use, not at import time or even at
plugin-registration time) so that loading this provider plugin - which
happens unconditionally during provider discovery - never itself
requires network access or valid credentials; only *using* the "telegram"
storage adapter does. `provider.py` is the only caller of this module.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RemoteFileRef:
    """Typed view of a `StorageRef(provider="telegram", ...)` payload -
    see `_mongo_shared/codecs.py` and the tests under `tests/unit/` for
    the on-the-wire shape (`{"chat_id": ..., "message_id": ...}`)."""

    chat_id: int
    message_id: int

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "RemoteFileRef":
        try:
            return cls(chat_id=int(payload["chat_id"]), message_id=int(payload["message_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                "telegram StorageRef payload must contain integer 'chat_id' and "
                "'message_id'"
            ) from exc


@dataclass(frozen=True)
class RemoteFileInfo:
    """Subset of a Telegram message's file attributes this adapter needs -
    intentionally not the raw pyrogram `Message` object, so nothing above
    this module ever touches a pyrogram type (mirrors why `StorageRef`
    payloads are opaque dicts rather than typed per-provider classes)."""

    file_id: str
    file_size: int
    mime_type: str
    file_name: str


class TelegramStreamClientPool:
    """Lazily-connecting, round-robin pool of kurigram `Client`s used only
    to read file bytes for streaming/download - never to send messages or
    check membership (that stays `TelegramGateway`'s job).

    With a single token (the common case - `STREAM_WORKER_TOKENS` unset),
    this degrades to a pool of one client, per the design doc's note that
    a single-token setup is a config state, not an architectural fork.
    """

    def __init__(self, api_id: int, api_hash: str, bot_tokens: tuple[str, ...]) -> None:
        if not bot_tokens:
            raise ValueError("TelegramStreamClientPool requires at least one bot token")
        self._api_id = api_id
        self._api_hash = api_hash
        self._bot_tokens = bot_tokens
        self._clients: list[Any] = []
        self._cycle: itertools.cycle | None = None
        self._connect_lock = asyncio.Lock()

    async def _ensure_connected(self) -> None:
        if self._clients:
            return
        async with self._connect_lock:
            if self._clients:  # re-check after acquiring the lock
                return
            # Imported lazily so importing this module (which happens at
            # provider-discovery time for every process, regardless of
            # STORAGE_PROVIDER) never requires `kurigram` to be installed -
            # only actually using this adapter does. Same rationale as
            # `telegram_kurigram/plugin.py`'s optional `telegram` extra.
            from pyrogram import Client

            for index, token in enumerate(self._bot_tokens):
                client = Client(
                    f"media_platform_stream_worker_{index}",
                    api_id=self._api_id,
                    api_hash=self._api_hash,
                    bot_token=token,
                    in_memory=True,
                )
                await client.start()
                self._clients.append(client)
            self._cycle = itertools.cycle(self._clients)
            logger.info("Streaming worker pool connected with %d client(s)", len(self._clients))

    async def _next_client(self) -> Any:
        await self._ensure_connected()
        assert self._cycle is not None
        return next(self._cycle)

    async def disconnect(self) -> None:
        for client in self._clients:
            await client.stop()
        self._clients.clear()
        self._cycle = None

    async def get_file_info(self, ref: RemoteFileRef) -> RemoteFileInfo:
        client = await self._next_client()
        messages = await client.get_messages(ref.chat_id, [ref.message_id])
        message = messages[0] if isinstance(messages, list) else messages
        media = message.document or message.video or message.audio or message.animation
        if media is None:
            raise ValueError(f"Message {ref.chat_id}:{ref.message_id} has no downloadable media")
        return RemoteFileInfo(
            file_id=media.file_id,
            file_size=getattr(media, "file_size", 0) or 0,
            mime_type=getattr(media, "mime_type", "application/octet-stream")
            or "application/octet-stream",
            file_name=getattr(media, "file_name", "") or "",
        )

    async def iter_bytes(
        self, ref: RemoteFileRef, *, offset: int, limit: int, chunk_size: int
    ) -> AsyncIterator[bytes]:
        """Yields bytes for `[offset, offset + limit)` of the file backing
        `ref`, in `chunk_size` pieces. Uses kurigram's high-level
        `stream_media(message, offset=..., limit=...)` generator (bytes
        already chunked at the transport layer at ~1MB per Telegram RPC
        call) rather than issuing raw `upload.GetFile` calls directly -
        it does the same "no full-file buffering" streaming the design
        doc calls for, without reimplementing kurigram's chunking/retry
        internals. `offset`/`limit` here are in bytes; kurigram's
        `stream_media` accepts them the same way.
        """
        client = await self._next_client()
        messages = await client.get_messages(ref.chat_id, [ref.message_id])
        message = messages[0] if isinstance(messages, list) else messages

        remaining = limit
        async for block in client.stream_media(message, offset=offset, limit=limit):
            if remaining <= 0:
                break
            piece = block[: min(len(block), remaining)] if remaining < len(block) else block
            remaining -= len(piece)
            yield piece
