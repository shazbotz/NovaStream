"""Plugin discovery, dependency ordering, and loading.

Discovers plugins by scanning a package (``plugins.providers`` or
``plugins.features``) for subpackages exposing a ``plugin`` module with a
module-level ``PLUGIN`` instance. No plugin needs to be imported by name
anywhere in core code - see architecture-design-phase1-v3.md §3 and
docs/guides/plugin-development.md.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Any

from media_platform.domain.errors import PluginError

logger = logging.getLogger(__name__)

PROVIDER_PACKAGE = "media_platform.plugins.providers"
FEATURE_PACKAGE = "media_platform.plugins.features"


def discover_plugins(package_name: str) -> list[Any]:
    plugins: list[Any] = []
    try:
        package = importlib.import_module(package_name)
    except ModuleNotFoundError:
        logger.warning("Plugin package '%s' not found, skipping", package_name)
        return plugins
    if not hasattr(package, "__path__"):
        return plugins
    for module_info in pkgutil.iter_modules(package.__path__):
        if not module_info.ispkg:
            continue
        plugin_module_name = f"{package_name}.{module_info.name}.plugin"
        try:
            plugin_module = importlib.import_module(plugin_module_name)
        except ModuleNotFoundError as exc:
            if exc.name == plugin_module_name:
                # This subpackage simply doesn't have a `plugin.py` -
                # it's not a plugin at all (e.g. a shared helper package).
                continue
            # The plugin module exists but one of *its* imports (a
            # third-party library like motor or kurigram) isn't
            # installed. This must not look the same as "not a plugin" -
            # skip it, but say why, so a missing optional dependency is
            # visible instead of silently making the provider disappear.
            logger.warning(
                "Skipping plugin '%s': missing dependency '%s'. Install "
                "it (see pyproject.toml optional-dependencies) if you "
                "need this provider - otherwise this warning is safe to "
                "ignore.",
                module_info.name,
                exc.name,
            )
            continue
        plugin = getattr(plugin_module, "PLUGIN", None)
        if plugin is None:
            raise PluginError(
                f"{plugin_module_name} does not define a module-level PLUGIN instance"
            )
        plugins.append(plugin)
    return plugins


def filter_disabled(plugins: list[Any], disabled: frozenset[str]) -> list[Any]:
    if not disabled:
        return plugins
    kept: list[Any] = []
    for plugin in plugins:
        if plugin.name in disabled:
            logger.info("Plugin '%s' disabled via PLUGINS_DISABLED, skipping", plugin.name)
            continue
        kept.append(plugin)
    return kept


def order_by_dependencies(plugins: list[Any]) -> list[Any]:
    by_name = {p.name: p for p in plugins}
    for plugin in plugins:
        for dep in plugin.requires:
            if dep not in by_name:
                raise PluginError(
                    f"Plugin '{plugin.name}' requires '{dep}', which is not loaded"
                )

    ordered: list[Any] = []
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(plugin: Any) -> None:
        if plugin.name in visited:
            return
        if plugin.name in visiting:
            raise PluginError(f"Circular plugin dependency involving '{plugin.name}'")
        visiting.add(plugin.name)
        for dep in plugin.requires:
            visit(by_name[dep])
        visiting.discard(plugin.name)
        visited.add(plugin.name)
        ordered.append(plugin)

    for plugin in plugins:
        visit(plugin)
    return ordered


class PluginManager:
    def __init__(self) -> None:
        self._loaded: list[Any] = []

    def load_package(
        self,
        package_name: str,
        ctx: Any,
        disabled: frozenset[str] = frozenset(),
    ) -> list[Any]:
        plugins = discover_plugins(package_name)
        plugins = filter_disabled(plugins, disabled)
        plugins = order_by_dependencies(plugins)
        for plugin in plugins:
            logger.info("Loading plugin '%s' v%s", plugin.name, plugin.version)
            try:
                plugin.register(ctx)
            except Exception as exc:
                raise PluginError(f"Plugin '{plugin.name}' failed to register") from exc
            self._loaded.append(plugin)
        return plugins

    def loaded_plugin_names(self) -> list[str]:
        return [p.name for p in self._loaded]
