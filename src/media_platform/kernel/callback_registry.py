"""Prefix-routed callback_data dispatch.

Replaces the O(n) `if data.startswith(...)` chain found in the reference
bots (architecture-design-phase1.md §1, Master-2's ~540-line cb_handler)
with a routing table: each plugin registers the prefix it owns, dispatch
picks the longest matching prefix.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

CallbackHandler = Callable[..., Awaitable[Any]]


class CallbackRegistry:
    def __init__(self) -> None:
        self._routes: dict[str, CallbackHandler] = {}

    def register(self, prefix: str, handler: CallbackHandler) -> None:
        if prefix in self._routes:
            raise ValueError(f"Callback prefix '{prefix}' is already registered")
        self._routes[prefix] = handler

    def resolve(self, data: str) -> CallbackHandler | None:
        best: str | None = None
        for prefix in self._routes:
            if data.startswith(prefix) and (best is None or len(prefix) > len(best)):
                best = prefix
        return self._routes.get(best) if best is not None else None

    def all_prefixes(self) -> list[str]:
        return sorted(self._routes)
