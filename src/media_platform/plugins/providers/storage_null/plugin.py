"""Registers the 'null' StorageProvider (file bytes) adapter.

Read/write operations raise ProviderError - there is no backend to
actually store or serve bytes from until a real adapter (telegram, s3,
r2, ...) is configured. See docs/architecture/storage.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator

from media_platform.domain.errors import ProviderError

if TYPE_CHECKING:
    from media_platform.domain.models import FileMetadata, StorageRef
    from media_platform.kernel.plugin import ProviderContext

_NOT_CONFIGURED = "No StorageProvider configured (STORAGE_PROVIDER=null)"


class NullStorageProvider:
    async def put(self, key: str, source: AsyncIterator[bytes]) -> "StorageRef":
        raise ProviderError(_NOT_CONFIGURED)

    async def get_range(
        self, ref: "StorageRef", start: int, end: int
    ) -> AsyncIterator[bytes]:
        # An async-generator function: the ProviderError below is raised
        # on first iteration (`async for chunk in ...`), not on call -
        # that's normal async-generator semantics, not a bug.
        raise ProviderError(_NOT_CONFIGURED)
        yield b""  # pragma: no cover - unreachable, satisfies generator typing

    async def get_metadata(self, ref: "StorageRef") -> "FileMetadata":
        raise ProviderError(_NOT_CONFIGURED)

    async def delete(self, ref: "StorageRef") -> None:
        pass


class StorageNullProviderPlugin:
    name = "provider.storage.null"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "ProviderContext") -> None:
        ctx.providers.register("storage", "null", NullStorageProvider)


PLUGIN = StorageNullProviderPlugin()
