"""Registers the 'mongo_text' SearchProvider adapter.

Requires the `mongo` extra (`pip install -e ".[mongo]"`) - missing
dependency is caught by plugin discovery as a warning, not a crash.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from media_platform.domain.errors import ConfigurationError
from media_platform.plugins.providers.search_mongo_text.provider import MongoSearchProvider

if TYPE_CHECKING:
    from media_platform.kernel.plugin import ProviderContext


class SearchMongoTextProviderPlugin:
    name = "provider.search.mongo_text"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "ProviderContext") -> None:
        def build() -> MongoSearchProvider:
            if not ctx.config.database_url:
                raise ConfigurationError(
                    "SEARCH_PROVIDER=mongo_text requires DATABASE_URL to be set"
                )
            return MongoSearchProvider(url=ctx.config.database_url)

        ctx.providers.register("search", "mongo_text", build)


PLUGIN = SearchMongoTextProviderPlugin()
