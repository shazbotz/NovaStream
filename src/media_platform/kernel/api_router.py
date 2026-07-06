"""HTTP route registry for the Mini App / future clients' JSON API.

Plugins register routes through this small abstraction instead of
importing aiohttp directly, so the HTTP library stays an implementation
detail confined to `server.py` - see architecture-design-phase1-v3.md §4.

This is enforced by the handler signature, not just convention: handlers
take an `ApiRequest` (a plain dataclass) and return an `ApiResponse` (a
plain dataclass) or raise a `domain.errors.PlatformError` subclass -
never an aiohttp `Request`/`Response`. `server.py` is the only place that
adapts a real aiohttp request into an `ApiRequest` and turns an
`ApiResponse` (or a caught `PlatformError`) back into an aiohttp
response, mapping error types to HTTP status codes in one place instead
of every handler doing its own try/except.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from media_platform.domain.errors import ValidationError


@dataclass(frozen=True)
class ApiRequest:
    query: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    path_params: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] | None = None


@dataclass(frozen=True)
class ApiResponse:
    body: dict[str, Any]
    status: int = 200


RouteHandler = Callable[[ApiRequest], Awaitable[ApiResponse]]


def parse_query_int(query: dict[str, str], key: str, *, default: int, minimum: int = 0) -> int:
    """Shared by every plugin that paginates via query params, so the
    "reject non-integers, reject negatives" behavior (and its error
    message) is consistent instead of reimplemented per plugin. Raises
    `domain.errors.ValidationError` - callers don't need to catch
    anything themselves; `server.py`'s error mapping handles it.
    """
    raw = query.get(key)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValidationError(f"'{key}' must be an integer, got '{raw}'") from exc
    if value < minimum:
        raise ValidationError(f"'{key}' must be >= {minimum}")
    return value


@dataclass(frozen=True)
class Route:
    method: str
    path: str
    handler: RouteHandler


class ApiRouter:
    def __init__(self) -> None:
        self._routes: list[Route] = []

    def get(self, path: str, handler: RouteHandler) -> None:
        self._add("GET", path, handler)

    def post(self, path: str, handler: RouteHandler) -> None:
        self._add("POST", path, handler)

    def _add(self, method: str, path: str, handler: RouteHandler) -> None:
        self._routes.append(Route(method=method, path=path, handler=handler))

    def routes(self) -> list[Route]:
        return list(self._routes)
