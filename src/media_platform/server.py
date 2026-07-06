"""Composition root.

The only module in the codebase allowed to import both a port interface
and reach for a concrete adapter by name, and to wire the two together.
Every other module reaches adapters only through `domain/interfaces.py`.

Boot sequence (see architecture-design-phase1-v3.md §3 for why loading is
split into two passes):

1. Load configuration (fail fast on invalid values).
2. Load *provider* plugins first - they only register adapter factories,
   they don't need services (services are built FROM providers).
3. Resolve the configured adapter for each port from the registry.
4. Build the core services from those adapters.
5. Load *feature* plugins, handing them the full context including the
   now-real services.
6. Start the HTTP server and the scheduler.
7. Wait for SIGTERM/SIGINT, then drain and exit.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

from aiohttp import web

from media_platform.cache.ttl_cache import TTLCache
from media_platform.config import Settings
from media_platform.domain.errors import (
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
    PermissionError_,
    ProviderError,
    ValidationError,
)
from media_platform.domain.models import FeatureFlag
from media_platform.kernel.api_router import ApiRequest, ApiResponse, ApiRouter, RouteHandler
from media_platform.kernel.callback_registry import CallbackRegistry
from media_platform.kernel.command_registry import CommandRegistry
from media_platform.kernel.model_registry import ModelRegistry
from media_platform.kernel.plugin import PluginContext, ProviderContext
from media_platform.kernel.plugin_manager import (
    FEATURE_PACKAGE,
    PROVIDER_PACKAGE,
    PluginManager,
)
from media_platform.kernel.provider_registry import ProviderRegistry
from media_platform.kernel.scheduler import Scheduler
from media_platform.kernel.service_locator import ServiceLocator
from media_platform.kernel.settings_registry import SettingsRegistry
from media_platform.lifecycle import Lifecycle
from media_platform.logging_setup import configure_logging
from media_platform.services import range_parsing, stream_tokens
from media_platform.services.catalog_service import CatalogService
from media_platform.services.feature_flags import FeatureFlagService
from media_platform.services.history_service import HistoryService
from media_platform.services.playback_service import PlaybackService

logger = logging.getLogger(__name__)

_ERROR_STATUS_MAP: dict[type[Exception], int] = {
    ValidationError: 400,
    AuthenticationError: 401,
    PermissionError_: 403,
    NotFoundError: 404,
    ProviderError: 502,
    ConfigurationError: 500,
}


def _adapt_to_aiohttp(handler: RouteHandler) -> Callable[[web.Request], Awaitable[web.Response]]:
    """Wraps a transport-independent `RouteHandler` (takes `ApiRequest`,
    returns `ApiResponse`) as an aiohttp handler. This is the only place
    in the codebase that translates between aiohttp's types and ours, and
    the only place HTTP status codes get decided for error cases - every
    feature plugin's handler just raises the right `PlatformError`
    subclass and never thinks about status codes or aiohttp at all.
    """

    async def aiohttp_handler(request: web.Request) -> web.Response:
        body: dict[str, object] | None = None
        if request.can_read_body:
            try:
                body = await request.json()
            except Exception:
                body = None

        api_request = ApiRequest(
            query=dict(request.query),
            headers=dict(request.headers),
            path_params=dict(request.match_info),
            body=body,
        )

        try:
            response = await handler(api_request)
        except tuple(_ERROR_STATUS_MAP) as exc:
            status = next(
                status for exc_type, status in _ERROR_STATUS_MAP.items() if isinstance(exc, exc_type)
            )
            return web.json_response({"error": str(exc)}, status=status)
        except Exception:
            # Anything else is a bug, not an expected/handleable error -
            # log the full traceback server-side, but never leak internal
            # exception details to the client (Phase 4 security review:
            # secure configuration / not exposing internals).
            logger.exception("Unhandled error in API route %s", request.path)
            return web.json_response({"error": "internal server error"}, status=500)

        return web.json_response(response.body, status=response.status)

    return aiohttp_handler


async def build_application() -> tuple[web.Application, Scheduler, Lifecycle, object]:
    """Builds (but does not start) the whole application. Split out from
    `main()` so tests can build an app instance without binding a socket.
    """
    settings = Settings.load()
    configure_logging(settings.log_level, settings.log_format)
    logger.info("Booting in '%s' environment", settings.environment)

    disabled = frozenset(settings.plugins_disabled)
    provider_registry = ProviderRegistry()
    plugin_manager = PluginManager()

    # --- Pass 1: provider plugins ---------------------------------------
    provider_ctx = ProviderContext(providers=provider_registry, config=settings)
    plugin_manager.load_package(PROVIDER_PACKAGE, provider_ctx, disabled=disabled)
    logger.info("Loaded providers: %s", plugin_manager.loaded_plugin_names())

    search = provider_registry.get("search", settings.search_provider)
    storage = provider_registry.get("storage", settings.storage_provider)
    database = provider_registry.get("database", settings.database_provider)
    auth = provider_registry.get("auth", settings.auth_provider)
    metadata = provider_registry.get("metadata", settings.metadata_provider)
    streaming = provider_registry.get("streaming", settings.streaming_provider)
    telegram = provider_registry.get("telegram", settings.telegram_provider)

    await database.connect()
    await telegram.connect()

    # --- Build core services from the resolved adapters ------------------
    cache: TTLCache[str, FeatureFlag] = TTLCache(
        max_size=settings.cache_max_size, ttl_seconds=settings.cache_ttl_seconds
    )
    flags = FeatureFlagService(
        repository=database.repository("feature_flags"), cache=cache
    )
    catalog = CatalogService(repository=database.repository("media"), search=search)
    playback = PlaybackService(streaming=streaming)
    history = HistoryService(repository=database.repository("watch_progress"))

    services = ServiceLocator(
        catalog=catalog,
        playback=playback,
        history=history,
        flags=flags,
        telegram=telegram,
        auth=auth,
        cache=cache,
    )

    # --- Pass 2: feature plugins ------------------------------------------
    commands = CommandRegistry()
    callbacks = CallbackRegistry()
    api = ApiRouter()
    scheduler = Scheduler()
    plugin_settings = SettingsRegistry()
    models = ModelRegistry()

    feature_ctx = PluginContext(
        providers=provider_registry,
        commands=commands,
        callbacks=callbacks,
        api=api,
        scheduler=scheduler,
        settings=plugin_settings,
        models=models,
        services=services,
    )
    plugin_manager.load_package(FEATURE_PACKAGE, feature_ctx, disabled=disabled)
    logger.info("Loaded features: %s", plugin_manager.loaded_plugin_names())

    # --- HTTP surface -------------------------------------------------------
    app = web.Application()
    app["settings"] = settings
    app["auth_provider"] = auth
    app["metadata_provider"] = metadata

    async def healthz(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "status": "ok",
                "environment": settings.environment,
                "providers": {
                    "search": settings.search_provider,
                    "storage": settings.storage_provider,
                    "database": settings.database_provider,
                    "auth": settings.auth_provider,
                    "metadata": settings.metadata_provider,
                    "streaming": settings.streaming_provider,
                    "telegram": settings.telegram_provider,
                },
                "plugins": plugin_manager.loaded_plugin_names(),
            }
        )

    async def stream(request: web.Request) -> web.StreamResponse:
        """Serves file bytes for a signed URL minted by the `streaming`
        feature plugin's `/api/stream-token/{id}` /
        `/api/download-token/{id}` routes.

        Registered directly on the aiohttp app, next to `/healthz`,
        rather than through `ApiRouter` - `ApiRouter`'s
        `ApiRequest`/`ApiResponse` pair is JSON-only by design (see
        `kernel/api_router.py`'s docstring) and has no way to express a
        binary, `Range`-aware, streamed response. This keeps that
        abstraction's contract simple for the ~10 JSON routes that use it
        instead of bending it to fit the one binary route, at the cost of
        this one handler talking to aiohttp types directly - the same
        trade-off already made for `/healthz`.
        """
        media_id = request.match_info.get("media_id", "")
        exp_raw = request.query.get("exp")
        sig = request.query.get("sig")
        user_raw = request.query.get("u")
        if not (media_id and exp_raw and sig and user_raw):
            return web.json_response(
                {"error": "Missing one of: exp, sig, u query parameters"}, status=400
            )
        try:
            expires_at = int(exp_raw)
            user_id = int(user_raw)
        except ValueError:
            return web.json_response({"error": "exp and u must be integers"}, status=400)

        if not settings.stream_secret:
            return web.json_response(
                {"error": "Streaming is not configured (STREAM_SECRET unset)"}, status=500
            )
        if not stream_tokens.verify(settings.stream_secret, media_id, user_id, expires_at, sig):
            return web.json_response({"error": "Invalid or tampered stream token"}, status=403)
        if expires_at < int(time.time()):
            return web.json_response({"error": "Stream token has expired"}, status=403)

        item = await catalog.get_item(media_id)
        if item is None:
            return web.json_response({"error": f"No media item with id '{media_id}'"}, status=404)

        file_size = item.file_size
        range_header = request.headers.get("Range")
        try:
            byte_range = range_parsing.parse_range(range_header, file_size)
        except range_parsing.MalformedRangeError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except range_parsing.UnsatisfiableRangeError:
            return web.Response(status=416, headers={"Content-Range": f"bytes */{file_size}"})
        start, end = byte_range.start, byte_range.end
        status = 206 if byte_range.is_partial else 200

        headers = {
            "Content-Type": item.mime_type or "application/octet-stream",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
        }
        if byte_range.is_partial:
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        if request.query.get("dl") == "1":
            headers["Content-Disposition"] = f'attachment; filename="{item.file_name}"'

        response = web.StreamResponse(status=status, headers=headers)
        await response.prepare(request)
        try:
            async for chunk in storage.get_range(item.storage_ref, start, end):
                await response.write(chunk)
        except ProviderError:
            logger.exception("Storage read failed while streaming media_id=%s", media_id)
            # Headers are already sent at this point (StreamResponse has
            # no way to change the status after `prepare()`) - closing
            # the connection is the only option left, same as any
            # streaming server hitting a backend error mid-response.
        await response.write_eof()
        return response

    app.router.add_get("/healthz", healthz)
    app.router.add_get("/stream/{media_id}", stream)
    for route in api.routes():
        aiohttp_handler = _adapt_to_aiohttp(route.handler)
        if route.method == "GET":
            app.router.add_get(route.path, aiohttp_handler)
        elif route.method == "POST":
            app.router.add_post(route.path, aiohttp_handler)
        else:
            raise ValueError(f"Unsupported HTTP method '{route.method}' for {route.path}")

    lifecycle = Lifecycle()
    lifecycle.on_shutdown(scheduler.stop)
    lifecycle.on_shutdown(telegram.disconnect)
    lifecycle.on_shutdown(database.disconnect)

    return app, scheduler, lifecycle, database


async def main() -> None:
    app, scheduler, lifecycle, _database = await build_application()
    settings: Settings = app["settings"]

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.http_host, settings.http_port)
    await site.start()
    logger.info("Listening on http://%s:%s", settings.http_host, settings.http_port)

    scheduler.start()

    loop = asyncio.get_running_loop()
    lifecycle.install_signal_handlers(loop)

    try:
        while not lifecycle.shutting_down:
            await asyncio.sleep(1)
    finally:
        logger.info("Draining connections and shutting down")
        await runner.cleanup()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
