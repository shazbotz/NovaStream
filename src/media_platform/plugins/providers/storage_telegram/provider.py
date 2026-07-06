"""Telegram-backed StorageProvider - see docs/architecture/storage.md.

Serves file bytes (for streaming and download) directly from the
Telegram chat/channel a file was originally uploaded to, addressed by the
`StorageRef(provider="telegram", payload={"chat_id": ..., "message_id":
...})` shape already used elsewhere in this codebase (see
`_mongo_shared/codecs.py` and the `storage_ref` fixtures throughout
`tests/unit/`).

**Verification status:** same caveat as `client.py` and
`telegram_kurigram/provider.py` - not exercised against real Telegram
servers in this environment (no `kurigram` install, no network, no live
bot token). Checked with `python -m py_compile` only.

`put()` deliberately raises `ProviderError`: this adapter is a read-path
adapter for bytes that already live in a Telegram chat (uploaded there by
the existing ingestion flow that populates `POST /api/media`'s
`storage_ref`, itself outside this adapter's scope - see
`catalog_search/plugin.py`). Writing new files *into* Telegram from this
adapter is separate, not-yet-scoped work; `NullStorageProvider.put()`
already establishes the same "raises rather than silently no-ops"
pattern for an unimplemented operation.
"""

from __future__ import annotations

from typing import AsyncIterator

from media_platform.domain.errors import NotFoundError, ProviderError
from media_platform.domain.models import FileMetadata, StorageRef
from media_platform.plugins.providers.storage_telegram.client import (
    RemoteFileRef,
    TelegramStreamClientPool,
)

_PUT_NOT_SUPPORTED = (
    "storage_telegram is a read-only adapter over files already uploaded to "
    "Telegram by the ingestion pipeline - it does not support put()"
)


class TelegramStorageProvider:
    def __init__(self, pool: TelegramStreamClientPool, chunk_size: int) -> None:
        self._pool = pool
        self._chunk_size = chunk_size

    async def put(self, key: str, source: AsyncIterator[bytes]) -> StorageRef:
        raise ProviderError(_PUT_NOT_SUPPORTED)

    async def get_range(self, ref: StorageRef, start: int, end: int) -> AsyncIterator[bytes]:
        if ref.provider != "telegram":
            raise ProviderError(
                f"storage_telegram cannot serve a StorageRef from provider '{ref.provider}'"
            )
        if start < 0 or end < start:
            raise ProviderError(f"Invalid byte range requested: {start}-{end}")

        remote_ref = self._as_remote_ref(ref)
        limit = end - start + 1
        try:
            async for chunk in self._pool.iter_bytes(
                remote_ref, offset=start, limit=limit, chunk_size=self._chunk_size
            ):
                yield chunk
        except ValueError as exc:
            raise NotFoundError(str(exc)) from exc
        except Exception as exc:  # pragma: no cover - real Telegram/pyrogram errors
            raise ProviderError(f"Telegram storage read failed: {exc}") from exc

    async def get_metadata(self, ref: StorageRef) -> FileMetadata:
        remote_ref = self._as_remote_ref(ref)
        try:
            info = await self._pool.get_file_info(remote_ref)
        except ValueError as exc:
            raise NotFoundError(str(exc)) from exc
        except Exception as exc:  # pragma: no cover - real Telegram/pyrogram errors
            raise ProviderError(f"Telegram storage metadata lookup failed: {exc}") from exc
        return FileMetadata(
            size=info.file_size, mime_type=info.mime_type, file_name=info.file_name
        )

    async def delete(self, ref: StorageRef) -> None:
        # Deleting the original Telegram message is a destructive,
        # channel-admin-level operation deliberately left to the (not yet
        # built) admin/ingestion tooling rather than the read-path
        # StorageProvider - see NullStorageProvider.delete() for the same
        # "accepted, no-op" stance at this phase.
        pass

    @staticmethod
    def _as_remote_ref(ref: StorageRef) -> RemoteFileRef:
        if ref.provider != "telegram":
            raise ProviderError(
                f"storage_telegram cannot serve a StorageRef from provider '{ref.provider}'"
            )
        try:
            return RemoteFileRef.from_payload(ref.payload)
        except ValueError as exc:
            raise ProviderError(str(exc)) from exc
