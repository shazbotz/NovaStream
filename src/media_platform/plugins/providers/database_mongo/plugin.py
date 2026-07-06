"""Registers the 'mongo' DatabaseProvider adapter.

Requires the `mongo` extra (`pip install -e ".[mongo]"`) - if `motor`
isn't installed, plugin discovery skips this with a warning rather than
crashing the whole application (see kernel/plugin_manager.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from media_platform.domain.errors import ConfigurationError
from media_platform.plugins.providers.database_mongo.provider import MongoDatabaseProvider

if TYPE_CHECKING:
    from media_platform.kernel.plugin import ProviderContext


class DatabaseMongoProviderPlugin:
    name = "provider.database.mongo"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "ProviderContext") -> None:
        def build() -> MongoDatabaseProvider:
            if not ctx.config.database_url:
                raise ConfigurationError(
                    "DATABASE_PROVIDER=mongo requires DATABASE_URL to be set"
                )
            return MongoDatabaseProvider(url=ctx.config.database_url)

        ctx.providers.register("database", "mongo", build)


PLUGIN = DatabaseMongoProviderPlugin()
