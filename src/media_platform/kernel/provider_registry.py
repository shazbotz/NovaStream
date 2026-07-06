"""Registry mapping (port, adapter name) -> factory.

Provider plugins (plugins/providers/*) register an adapter here instead of
the composition root hardcoding imports for every backend - see
architecture-design-phase1-v3.md §3. `server.py` resolves the configured
adapter for each port by name, once, at startup.
"""

from __future__ import annotations

from typing import Any, Callable

from media_platform.domain.errors import ConfigurationError

Factory = Callable[[], Any]


class ProviderRegistry:
    def __init__(self) -> None:
        self._factories: dict[tuple[str, str], Factory] = {}

    def register(self, port: str, name: str, factory: Factory) -> None:
        key = (port, name)
        if key in self._factories:
            raise ConfigurationError(
                f"Provider '{name}' is already registered for port '{port}'"
            )
        self._factories[key] = factory

    def get(self, port: str, name: str) -> Any:
        try:
            factory = self._factories[(port, name)]
        except KeyError as exc:
            available = self.available(port)
            raise ConfigurationError(
                f"No provider named '{name}' registered for port '{port}'. "
                f"Available for '{port}': {available or '(none loaded)'}"
            ) from exc
        return factory()

    def available(self, port: str) -> list[str]:
        return sorted(name for p, name in self._factories if p == port)
