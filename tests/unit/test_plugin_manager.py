"""Unit tests for plugin discovery and dependency ordering."""

from dataclasses import dataclass, field

import pytest

from media_platform.domain.errors import PluginError
from media_platform.kernel.plugin_manager import (
    PROVIDER_PACKAGE,
    discover_plugins,
    order_by_dependencies,
)


@dataclass
class _FakePlugin:
    name: str
    requires: tuple = field(default_factory=tuple)
    version: str = "0.1.0"
    registered_with: list = field(default_factory=list)

    def register(self, ctx):
        self.registered_with.append(ctx)


def test_order_by_dependencies_respects_requires():
    a = _FakePlugin(name="a")
    b = _FakePlugin(name="b", requires=("a",))
    c = _FakePlugin(name="c", requires=("b",))
    ordered = order_by_dependencies([c, b, a])
    assert [p.name for p in ordered] == ["a", "b", "c"]


def test_order_by_dependencies_missing_dependency_raises():
    a = _FakePlugin(name="a", requires=("ghost",))
    with pytest.raises(PluginError, match="ghost"):
        order_by_dependencies([a])


def test_order_by_dependencies_cycle_raises():
    a = _FakePlugin(name="a", requires=("b",))
    b = _FakePlugin(name="b", requires=("a",))
    with pytest.raises(PluginError, match="Circular"):
        order_by_dependencies([a, b])


def test_discover_plugins_finds_all_bootstrap_provider_plugins():
    # Exercises the real plugins/providers package on disk, not a fake -
    # this is what proves the discovery mechanism (pkgutil + a `plugin`
    # module + a `PLUGIN` instance) actually works end to end.
    plugins = discover_plugins(PROVIDER_PACKAGE)
    names = sorted(p.name for p in plugins)
    assert names == [
        "provider.auth.null",
        "provider.database.memory",
        "provider.metadata.null",
        "provider.search.null",
        "provider.storage.null",
        "provider.storage.telegram",
        "provider.streaming.null",
        "provider.streaming.signed",
        "provider.telegram.null",
    ]


def test_discover_plugins_missing_package_warns_and_returns_empty():
    assert discover_plugins("media_platform.plugins.does_not_exist") == []


def test_discover_plugins_skips_plugin_with_missing_dependency_without_crashing(
    tmp_path, monkeypatch
):
    """A plugin whose `plugin.py` itself fails to import (its own
    third-party dependency isn't installed) must be skipped with a
    warning - not confused with 'this subpackage isn't a plugin', and
    not allowed to crash discovery of every other plugin in the package.
    """
    package_root = tmp_path / "fake_provider_package"
    good_plugin_dir = package_root / "good_plugin"
    broken_plugin_dir = package_root / "broken_plugin"
    not_a_plugin_dir = package_root / "just_a_helper"

    for d in (package_root, good_plugin_dir, broken_plugin_dir, not_a_plugin_dir):
        d.mkdir(parents=True)
        (d / "__init__.py").write_text("")

    (good_plugin_dir / "plugin.py").write_text(
        "class P:\n"
        "    name = 'fake.good'\n"
        "    version = '0.1.0'\n"
        "    requires = ()\n"
        "    def register(self, ctx): pass\n"
        "PLUGIN = P()\n"
    )
    (broken_plugin_dir / "plugin.py").write_text(
        "import this_third_party_dependency_does_not_exist\n"
        "PLUGIN = object()\n"
    )
    # `just_a_helper` deliberately has no plugin.py at all.

    monkeypatch.syspath_prepend(str(tmp_path))
    plugins = discover_plugins("fake_provider_package")

    assert [p.name for p in plugins] == ["fake.good"]
