"""Scheduled/periodic job registry.

Bootstrap implementation: jobs run on plain asyncio tasks started from
server.py's lifecycle. The interface (`every`, `start`, `stop`) doesn't
change if this is later swapped for a real job queue - plugins never
touch asyncio directly.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

Job = Callable[[], Awaitable[None]]


@dataclass
class ScheduledJob:
    name: str
    interval_seconds: float
    func: Job


class Scheduler:
    def __init__(self) -> None:
        self._jobs: list[ScheduledJob] = []
        self._tasks: list[asyncio.Task[None]] = []

    def every(self, interval_seconds: float, name: str, func: Job) -> None:
        self._jobs.append(
            ScheduledJob(name=name, interval_seconds=interval_seconds, func=func)
        )

    def start(self) -> None:
        for job in self._jobs:
            self._tasks.append(asyncio.create_task(self._run_forever(job)))

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

    async def _run_forever(self, job: ScheduledJob) -> None:
        while True:
            await asyncio.sleep(job.interval_seconds)
            try:
                await job.func()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Scheduled job '%s' raised", job.name)

    def job_names(self) -> list[str]:
        return [job.name for job in self._jobs]
