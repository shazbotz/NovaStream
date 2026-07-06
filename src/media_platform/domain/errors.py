"""Application-wide exception hierarchy.

Every error a service or adapter raises should be one of these (or a
subclass of one of these), never a bare ``Exception`` or a third-party
library's exception type leaking across a layer boundary. That's what lets
``kernel/api_router.py`` and ``kernel/command_registry.py`` translate errors
into transport-appropriate responses in one place instead of every handler
needing its own try/except.
"""

from __future__ import annotations


class PlatformError(Exception):
    """Base class for every error raised by this application."""


class NotFoundError(PlatformError):
    """A requested entity does not exist."""


class ValidationError(PlatformError):
    """Caller-supplied input failed validation."""


class ProviderError(PlatformError):
    """An adapter (search/storage/database/auth/metadata/streaming) failed.

    Adapters should wrap their own library's exceptions in this (or a
    subclass of this) rather than letting e.g. a raw pymongo or aiohttp
    exception escape into ``services/``.
    """


class ConfigurationError(PlatformError):
    """Required configuration is missing or invalid. Raised at startup so
    the process fails fast instead of misbehaving at request time."""


class PluginError(PlatformError):
    """A plugin failed to load or register."""


class AuthenticationError(PlatformError):
    """Credentials could not be verified."""


class PermissionError_(PlatformError):
    """Caller is authenticated but not permitted to perform this action.

    Named with a trailing underscore to avoid shadowing the builtin
    ``PermissionError``.
    """
