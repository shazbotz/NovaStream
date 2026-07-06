"""Shared authentication helper for feature plugins.

Extracted after the same authenticate-or-401 logic showed up in a second
plugin (continue_watching) - see docs/guides/coding-standards.md's note
on duplication as a refactoring signal.

Deliberately takes `Credentials` (a transport-agnostic domain type), not
an HTTP-specific `ApiRequest` - `services/` must never import from
`kernel/` (enforced by `pyproject.toml`'s `[tool.importlinter]`
contracts; this function briefly violated that by taking an `ApiRequest`
parameter in an earlier draft, caught before shipping). Extracting a
bearer token out of an `ApiRequest`'s headers stays in the plugin/HTTP
layer, which already has that type - see `bearer_credentials` below,
called from each plugin with its own already-available `request.headers`.
"""

from __future__ import annotations

from media_platform.domain.errors import AuthenticationError
from media_platform.domain.interfaces import AuthProvider
from media_platform.domain.models import AuthenticatedPrincipal, Credentials


async def require_authenticated(
    auth: AuthProvider, credentials: Credentials
) -> AuthenticatedPrincipal:
    """Raises `AuthenticationError` (mapped to HTTP 401 by `server.py`) if
    `credentials` don't authenticate against the configured
    `AuthProvider`. Callers get back a real `AuthenticatedPrincipal` -
    use `.user_id` rather than trusting a client-supplied user id from a
    query string or request body, which would let one user read or write
    another user's data.
    """
    principal = await auth.authenticate(credentials)
    if principal is None:
        raise AuthenticationError("Authentication required")
    return principal


def bearer_credentials(headers: dict[str, str]) -> Credentials:
    """Small, transport-specific adapter: pulls a bearer token out of
    plain HTTP headers into a `Credentials` object. Takes a plain dict
    (not an `ApiRequest`) so this module stays free of any HTTP-specific
    import - a plugin calls this with `request.headers`, which it already
    has.
    """
    return Credentials(kind="bearer", payload={"token": headers.get("Authorization", "")})
