"""Environment-based configuration, validated at startup.

Required settings fail fast with a clear error instead of silently
falling back to a placeholder value that looks real - the failure mode
found in the reference bots' config module (architecture-design-phase1.md
§1: hardcoded fallback admin/channel IDs). This is the ONLY module allowed
to read `os.environ` - every other module receives configuration through
a `Settings` instance instead of reading the environment itself.

Deliberately stdlib-only (no pydantic-settings) to keep the bootstrap's
dependency footprint minimal on a 512MB budget - see
architecture-design-phase1.md §2. Swappable for a validation library later
without any other module changing, since this file is the only caller of
`os.environ`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from media_platform.domain.errors import ConfigurationError


def _optional(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _optional_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(
            f"Environment variable '{name}' must be an integer, got '{raw}'"
        ) from exc


@dataclass(frozen=True)
class Settings:
    environment: str
    http_host: str
    http_port: int
    log_level: str
    log_format: str

    search_provider: str
    storage_provider: str
    database_provider: str
    auth_provider: str
    metadata_provider: str
    streaming_provider: str
    telegram_provider: str

    cache_max_size: int
    cache_ttl_seconds: float

    plugins_disabled: tuple[str, ...] = field(default_factory=tuple)

    bot_token: str | None = None
    api_id: int | None = None
    api_hash: str | None = None
    database_url: str | None = None

    # --- Streaming (see docs/architecture/streaming.md) ------------------
    # Only read by the `streaming_signed` / `storage_telegram` provider
    # plugins (STREAMING_PROVIDER=signed / STORAGE_PROVIDER=telegram) -
    # the bootstrap 'null' adapters never touch these. `stream_secret`
    # deliberately has no default: an adapter that needs it fails fast at
    # its own provider-plugin load time (ConfigurationError), same pattern
    # as `bot_token`/`api_id`/`api_hash` above - see `Settings.load`'s
    # docstring.
    stream_secret: str | None = None
    public_base_url: str = "http://localhost:8080"
    stream_url_expiry_seconds: int = 21600
    stream_chunk_size: int = 1024 * 1024
    stream_worker_tokens: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def load(cls) -> "Settings":
        """Loads and validates configuration from the environment.

        The bootstrap phase defaults every provider to a 'null'/'memory'
        adapter so the application can start with zero external
        credentials configured (see docs/guides/deployment.md). Selecting
        a real adapter (e.g. STORAGE_PROVIDER=telegram) without its
        required credentials (e.g. BOT_TOKEN) fails fast inside *that*
        adapter's own provider plugin at load time, not here - only that
        adapter knows what it actually needs.
        """
        disabled_raw = _optional("PLUGINS_DISABLED", "")
        plugins_disabled = tuple(p.strip() for p in disabled_raw.split(",") if p.strip())

        return cls(
            environment=_optional("ENVIRONMENT", "development"),
            http_host=_optional("HTTP_HOST", "0.0.0.0"),
            http_port=_optional_int("HTTP_PORT", 8080),
            log_level=_optional("LOG_LEVEL", "INFO"),
            log_format=_optional("LOG_FORMAT", "text"),
            search_provider=_optional("SEARCH_PROVIDER", "null"),
            storage_provider=_optional("STORAGE_PROVIDER", "null"),
            database_provider=_optional("DATABASE_PROVIDER", "memory"),
            auth_provider=_optional("AUTH_PROVIDER", "null"),
            metadata_provider=_optional("METADATA_PROVIDER", "null"),
            streaming_provider=_optional("STREAMING_PROVIDER", "null"),
            telegram_provider=_optional("TELEGRAM_PROVIDER", "null"),
            cache_max_size=_optional_int("CACHE_MAX_SIZE", 512),
            cache_ttl_seconds=float(_optional_int("CACHE_TTL_SECONDS", 300)),
            plugins_disabled=plugins_disabled,
            bot_token=os.environ.get("BOT_TOKEN") or None,
            api_id=_optional_int("API_ID", 0) or None,
            api_hash=os.environ.get("API_HASH") or None,
            database_url=os.environ.get("DATABASE_URL") or None,
            stream_secret=os.environ.get("STREAM_SECRET") or None,
            public_base_url=_optional("PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/"),
            stream_url_expiry_seconds=_optional_int("STREAM_URL_EXPIRY_SECONDS", 21600),
            stream_chunk_size=_optional_int("STREAM_CHUNK_SIZE", 1024 * 1024),
            stream_worker_tokens=tuple(
                t.strip()
                for t in _optional("STREAM_WORKER_TOKENS", "").split(",")
                if t.strip()
            ),
        )
