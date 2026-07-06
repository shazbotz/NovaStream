"""Catalog variant grouping - presentation layer only.

Groups multiple `CatalogItem`s that are different file variants of the
same movie/series (different language/quality/codec/release) under one
display entry, instead of search results showing one row per file.

This module does NOT touch `SearchProvider`, `StorageProvider`,
`StreamingService`, or `CatalogService`'s existing methods - it operates
entirely on `CatalogItem` objects already fetched through
`CatalogService.get_item()`, per this enhancement's own constraint (group
by enhancing presentation only).

Flow this enables (see `plugin.py`'s `api_search`/`cmd_search` for how
each transport renders it):

    Search -> Movie (one entry per title+year) -> variants (language,
    quality, codec, release type, file size) -> Stream/Download

If a movie has exactly one variant, `GroupedTitle.is_single_variant` is
the signal for a caller to skip the selection step and go straight to
that variant - see `cmd_search` for a worked example.

Known, accepted limitation: grouping happens on an already-paginated page
of raw search hits (`SearchQuery.offset`/`limit` apply to raw files, not
groups), because the search engine itself isn't group-aware and this
enhancement is explicitly scoped not to change it. In rare cases a
movie's variants can be split across two pages. Making this fully correct
would need the search index itself to be group-aware, which is out of
scope for a presentation-only enhancement.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from media_platform.domain.models import CatalogItem


def normalize_title(title: str) -> str:
    """Lowercase, replace punctuation with a space (not remove it - "Iron-Man"
    must normalize to "iron man", not "ironman", or it won't match "Iron
    Man"), collapse whitespace. Enough for 'The Matrix' and
    'the   matrix!' to group together. Does not strip leading articles,
    transliterate, or fuzzy-match - a reasonable baseline, not a complete
    solution. Revisit if real-world grouping quality turns out to need
    more than this.
    """
    normalized = re.sub(r"[^\w\s]", " ", title.lower())
    return re.sub(r"\s+", " ", normalized).strip()


@dataclass(frozen=True)
class Variant:
    media_id: str
    language: str | None
    quality: str | None
    codec: str | None
    release_type: str | None
    file_size: int


@dataclass(frozen=True)
class GroupedTitle:
    title: str
    year: int | None
    variants: tuple[Variant, ...]

    @property
    def languages(self) -> list[str]:
        return sorted({v.language for v in self.variants if v.language})

    @property
    def qualities(self) -> list[str]:
        return sorted({v.quality for v in self.variants if v.quality})

    @property
    def is_single_variant(self) -> bool:
        return len(self.variants) == 1


def group_catalog_items(items: list[CatalogItem]) -> list[GroupedTitle]:
    """Groups by normalized title + release year, preserving the order in
    which each group was first seen (so grouping doesn't silently re-rank
    search results - the first-ranked hit's title still leads).
    """
    grouped: dict[tuple[str, int | None], list[CatalogItem]] = defaultdict(list)
    order: list[tuple[str, int | None]] = []

    for item in items:
        key = (normalize_title(item.title), item.year)
        if key not in grouped:
            order.append(key)
        grouped[key].append(item)

    results: list[GroupedTitle] = []
    for key in order:
        group_items = grouped[key]
        display_title = group_items[0].title  # first-seen original casing
        variants = tuple(
            Variant(
                media_id=i.id,
                language=i.language,
                quality=i.quality,
                codec=i.codec,
                release_type=i.release_type,
                file_size=i.file_size,
            )
            for i in group_items
        )
        results.append(GroupedTitle(title=display_title, year=key[1], variants=variants))
    return results
