"""Application lifecycle: startup/shutdown coordination.

Handles SIGTERM/SIGINT by running registered shutdown hooks - Koyeb sends
SIGTERM with roughly a 30s grace period before SIGKILL, so in-flight work
(the scheduler, open database connections) gets a chance to stop cleanly
instead of being hard-killed. See architecture-design-phase1.md §7.

Kept independent of any specific transport (HTTP server, bot polling
loop) so both can register shutdown hooks here rather than each managing
its own signal handling.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

ShutdownHook = Callable[[], Awaitable[None]]


class Lifecycle:
    def __init__(self) -> None:
        self._shutdown_hooks: list[ShutdownHook] = []
        self._shutting_down = asyncio.Event()

    def on_shutdown(self, hook: ShutdownHook) -> None:
        self._shutdown_hooks.append(hook)

    def install_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(
                    sig, lambda s=sig: asyncio.ensure_future(self._handle_signal(s))
                )
            except NotImplementedError:
                logger.warning("Signal handlers are not supported on this platform")

    async def _handle_signal(self, sig: "signal.Signals") -> None:
        if self._shutting_down.is_set():
            return
        logger.info("Received %s, shutting down gracefully", sig.name)
        self._shutting_down.set()
        for hook in self._shutdown_hooks:
            try:
                await hook()
            except Exception:
                logger.exception("Shutdown hook failed")

    @property
    def shutting_down(self) -> bool:
        return self._shutting_down.is_set()
