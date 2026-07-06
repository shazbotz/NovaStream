"""Registers the 'null' MetadataProvider adapter - always returns no
metadata found. Replace with imdb/tmdb/anilist/musicbrainz/etc. in
Phase 3 - each feature plugin can bring its own metadata provider.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from media_platform.domain.models import MetadataResult
    from media_platform.kernel.plugin import ProviderContext


class NullMetadataProvider:
    async def lookup(self, title: str, year: int | None = None) -> "MetadataResult | None":
        return None


class MetadataNullProviderPlugin:
    name = "provider.metadata.null"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "ProviderContext") -> None:
        ctx.providers.register("metadata", "null", NullMetadataProvider)


PLUGIN = MetadataNullProviderPlugin()
