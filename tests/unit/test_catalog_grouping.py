"""Unit tests for catalog variant grouping (grouping.py).

Pure-function tests, no database/search dependency - exactly what a
presentation-only enhancement should be testable with.
"""

from media_platform.domain.models import CatalogItem, StorageRef
from media_platform.plugins.features.catalog_search.grouping import (
    group_catalog_items,
    normalize_title,
)


def _item(id: str, title: str, **kwargs) -> CatalogItem:
    defaults = dict(
        file_name=f"{id}.mkv",
        file_size=1000,
        mime_type="video/x-matroska",
        storage_ref=StorageRef(provider="telegram", payload={}),
    )
    defaults.update(kwargs)
    return CatalogItem(id=id, title=title, **defaults)


def test_normalize_title_ignores_case_punctuation_and_whitespace():
    assert normalize_title("The Matrix") == normalize_title("the   matrix!")
    assert normalize_title("Iron-Man") == normalize_title("Iron Man")


def test_single_item_produces_a_single_group_with_one_variant():
    items = [_item("a", "Inception", year=2010, language="en", quality="1080p")]
    groups = group_catalog_items(items)

    assert len(groups) == 1
    assert groups[0].title == "Inception"
    assert groups[0].year == 2010
    assert groups[0].is_single_variant is True
    assert len(groups[0].variants) == 1


def test_multiple_variants_of_the_same_movie_group_into_one_entry():
    items = [
        _item("a", "Inception", year=2010, language="en", quality="1080p", codec="x264"),
        _item("b", "Inception", year=2010, language="hi", quality="720p", codec="HEVC"),
        _item("c", "Inception", year=2010, language="en", quality="4K", codec="AV1"),
    ]
    groups = group_catalog_items(items)

    assert len(groups) == 1
    group = groups[0]
    assert group.is_single_variant is False
    assert len(group.variants) == 3
    assert group.languages == ["en", "hi"]  # deduplicated, sorted
    assert group.qualities == ["1080p", "4K", "720p"]  # sorted lexically


def test_title_grouping_is_case_and_punctuation_insensitive():
    items = [
        _item("a", "The Matrix", year=1999),
        _item("b", "the matrix!", year=1999),
    ]
    groups = group_catalog_items(items)
    assert len(groups) == 1
    assert len(groups[0].variants) == 2


def test_same_title_different_year_does_not_group_together():
    """Different years -> different movies (e.g. a remake) - must not be
    merged just because the titles match."""
    items = [
        _item("a", "The Lion King", year=1994),
        _item("b", "The Lion King", year=2019),
    ]
    groups = group_catalog_items(items)
    assert len(groups) == 2
    assert {g.year for g in groups} == {1994, 2019}


def test_missing_year_is_its_own_group_not_merged_with_a_dated_one():
    items = [
        _item("a", "Some Movie", year=None),
        _item("b", "Some Movie", year=2020),
    ]
    groups = group_catalog_items(items)
    assert len(groups) == 2


def test_group_order_follows_first_appearance_not_alphabetical():
    items = [
        _item("a", "Zebra Movie", year=2001),
        _item("b", "Apple Movie", year=2002),
    ]
    groups = group_catalog_items(items)
    assert [g.title for g in groups] == ["Zebra Movie", "Apple Movie"]


def test_display_title_uses_first_seen_original_casing():
    items = [
        _item("a", "THE MATRIX", year=1999),
        _item("b", "the matrix", year=1999),
    ]
    groups = group_catalog_items(items)
    assert groups[0].title == "THE MATRIX"


def test_variants_carry_codec_and_release_type_and_file_size():
    items = [
        _item(
            "a", "Dune", year=2021, codec="HEVC", release_type="BluRay", file_size=4_000_000_000
        )
    ]
    groups = group_catalog_items(items)
    variant = groups[0].variants[0]
    assert variant.codec == "HEVC"
    assert variant.release_type == "BluRay"
    assert variant.file_size == 4_000_000_000


def test_empty_input_produces_no_groups():
    assert group_catalog_items([]) == []
