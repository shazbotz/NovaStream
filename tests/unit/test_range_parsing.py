"""Unit tests for media_platform.services.range_parsing."""

import pytest

from media_platform.services.range_parsing import (
    MalformedRangeError,
    UnsatisfiableRangeError,
    parse_range,
)


def test_no_range_header_returns_whole_file():
    r = parse_range(None, file_size=1000)
    assert (r.start, r.end, r.is_partial) == (0, 999, False)


def test_non_bytes_range_header_is_ignored():
    r = parse_range("items=0-1", file_size=1000)
    assert r.is_partial is False


def test_explicit_start_and_end():
    r = parse_range("bytes=100-199", file_size=1000)
    assert (r.start, r.end, r.is_partial) == (100, 199, True)


def test_open_ended_range_goes_to_end_of_file():
    r = parse_range("bytes=900-", file_size=1000)
    assert (r.start, r.end, r.is_partial) == (900, 999, True)


def test_suffix_range_serves_the_final_n_bytes():
    r = parse_range("bytes=-500", file_size=1000)
    assert (r.start, r.end, r.is_partial) == (500, 999, True)


def test_suffix_range_larger_than_file_clamps_to_start():
    r = parse_range("bytes=-5000", file_size=1000)
    assert (r.start, r.end, r.is_partial) == (0, 999, True)


def test_multi_range_is_rejected_as_malformed():
    with pytest.raises(MalformedRangeError):
        parse_range("bytes=0-99,200-299", file_size=1000)


def test_non_numeric_range_is_malformed():
    with pytest.raises(MalformedRangeError):
        parse_range("bytes=abc-def", file_size=1000)


def test_empty_range_spec_is_malformed():
    with pytest.raises(MalformedRangeError):
        parse_range("bytes=-", file_size=1000)


def test_start_after_end_is_unsatisfiable():
    with pytest.raises(UnsatisfiableRangeError):
        parse_range("bytes=500-100", file_size=1000)


def test_end_beyond_file_size_is_unsatisfiable():
    with pytest.raises(UnsatisfiableRangeError):
        parse_range("bytes=0-9999", file_size=1000)


def test_zero_length_suffix_range_is_malformed():
    with pytest.raises(MalformedRangeError):
        parse_range("bytes=-0", file_size=1000)


def test_zero_size_file_is_unsatisfiable_for_any_range():
    with pytest.raises(UnsatisfiableRangeError):
        parse_range("bytes=0-0", file_size=0)
