"""Bounded, TTL-based cache.

Every long-lived cache in this codebase (search-result cache, membership
cache, pagination/session state, file-metadata cache) uses this instead of
an unbounded module-level dict - see architecture-design-phase1.md §4.5
for the failure mode this replaces (a daily process restart papering over
unbounded memory growth instead of fixing it).

In-process only: on a single instance this is globally consistent by
definition. If you ever run more than one instance, swap the backing
store for Redis behind this same interface without changing any caller -
see architecture-design-phase1-v2.md §2.5's scale-up note.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from threading import Lock
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    def __init__(self, max_size: int = 256, ttl_seconds: float = 300.0) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._data: "OrderedDict[K, tuple[float, V]]" = OrderedDict()
        self._lock = Lock()

    def get(self, key: K) -> V | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < time.monotonic():
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: K, value: V) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = (time.monotonic() + self._ttl_seconds, value)
            while len(self._data) > self._max_size:
                self._data.popitem(last=False)

    def delete(self, key: K) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
