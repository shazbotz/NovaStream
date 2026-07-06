"""Registers the 'null' AuthProvider adapter - authentication always
returns None (nobody is authenticated). Safe default until a real adapter
(telegram_init_data, api_key, oauth, ...) is configured - see
docs/architecture/auth.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from media_platform.domain.models import AuthenticatedPrincipal, Credentials
    from media_platform.kernel.plugin import ProviderContext


class NullAuthProvider:
    async def authenticate(self, credentials: "Credentials") -> "AuthenticatedPrincipal | None":
        return None


class AuthNullProviderPlugin:
    name = "provider.auth.null"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: "ProviderContext") -> None:
        ctx.providers.register("auth", "null", NullAuthProvider)


PLUGIN = AuthNullProviderPlugin()
