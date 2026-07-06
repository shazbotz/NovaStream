"""Registry for Telegram bot commands.

Feature plugins register command handlers here instead of the bot core
importing each plugin's handler module by name - see
docs/guides/plugin-development.md.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

CommandHandler = Callable[..., Awaitable[Any]]


class CommandRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, CommandHandler] = {}

    def register(self, command: str, handler: CommandHandler) -> None:
        key = command.lstrip("/").lower()
        if key in self._handlers:
            raise ValueError(f"Command '/{key}' is already registered")
        self._handlers[key] = handler

    def get(self, command: str) -> CommandHandler | None:
        return self._handlers.get(command.lstrip("/").lower())

    def all_commands(self) -> list[str]:
        return sorted(self._handlers)
