"""Registry for plugin-declared, admin-configurable settings.

This bootstrap phase only defines the declaration surface (key, default,
description). Actually editing values through an admin UI is feature
work for the admin_dashboard plugin (Phase 3+).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    default: Any
    description: str = ""


class SettingsRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, SettingDefinition] = {}

    def register(self, key: str, default: Any, description: str = "") -> None:
        if key in self._definitions:
            raise ValueError(f"Setting '{key}' is already registered")
        self._definitions[key] = SettingDefinition(
            key=key, default=default, description=description
        )

    def all(self) -> list[SettingDefinition]:
        return sorted(self._definitions.values(), key=lambda d: d.key)
