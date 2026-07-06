"""Registers the 'memory' DatabaseProvider adapter - functional,
in-process, non-persistent. Default in development. Replace with
mongo/postgres in Phase 3 - see docs/architecture/storage.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from media_platform.plugins.providers.database_memory.provider import (
    InMemoryDatabaseProvider,
)

if TYPE_CHECKING:
    from media_platform.kernel.plugin import ProviderContext


class DatabaseMemoryProviderPlugin:
    name = "provider.database.memory"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "ProviderContext") -> None:
        ctx.providers.register("database", "memory", InMemoryDatabaseProvider)


PLUGIN = DatabaseMemoryProviderPlugin()
