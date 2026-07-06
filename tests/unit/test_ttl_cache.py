"""Unit tests for the bounded TTL cache (media_platform.cache.ttl_cache).

This is the module that replaces every unbounded global dict found in the
reference bots (architecture-design-phase1.md §4.5) - it's worth testing
directly since correctness here is what makes the "no more daily restart"
claim true.
"""

import time

import pytest

from media_platform.cache.ttl_cache import TTLCache


def test_set_then_get_returns_value():
    cache: TTLCache[str, int] = TTLCache(max_size=10, ttl_seconds=60)
    cache.set("a", 1)
    assert cache.get("a") == 1


def test_missing_key_returns_none():
    cache: TTLCache[str, int] = TTLCache(max_size=10, ttl_seconds=60)
    assert cache.get("missing") is None


def test_expired_entry_returns_none():
    cache: TTLCache[str, int] = TTLCache(max_size=10, ttl_seconds=0.05)
    cache.set("a", 1)
    time.sleep(0.1)
    assert cache.get("a") is None


def test_bounded_size_evicts_least_recently_used():
    cache: TTLCache[str, int] = TTLCache(max_size=2, ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)  # should evict "a", the least recently used
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3
    assert len(cache) == 2


def test_get_refreshes_recency():
    cache: TTLCache[str, int] = TTLCache(max_size=2, ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")  # "a" is now more recently used than "b"
    cache.set("c", 3)  # should evict "b", not "a"
    assert cache.get("a") == 1
    assert cache.get("b") is None


def test_delete_and_clear():
    cache: TTLCache[str, int] = TTLCache(max_size=10, ttl_seconds=60)
    cache.set("a", 1)
    cache.delete("a")
    assert cache.get("a") is None

    cache.set("b", 2)
    cache.set("c", 3)
    cache.clear()
    assert len(cache) == 0


def test_rejects_invalid_construction():
    with pytest.raises(ValueError):
        TTLCache(max_size=0, ttl_seconds=60)
    with pytest.raises(ValueError):
        TTLCache(max_size=10, ttl_seconds=0)
