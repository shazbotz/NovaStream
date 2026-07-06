"""Registry letting plugins declare the persistence collections/models they
own, without importing a concrete DatabaseProvider adapter. A real schema
(dataclass, validation rules) is attached when the owning plugin is
implemented - this bootstrap phase only defines the declaration surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelDefinition:
    name: str
    schema: Any = None


class ModelRegistry:
    def __init__(self) -> None:
        self._models: dict[str, ModelDefinition] = {}

    def register(self, name: str, schema: Any = None) -> None:
        if name in self._models:
            raise ValueError(f"Model/collection '{name}' is already registered")
        self._models[name] = ModelDefinition(name=name, schema=schema)

    def all(self) -> list[ModelDefinition]:
        return sorted(self._models.values(), key=lambda m: m.name)
