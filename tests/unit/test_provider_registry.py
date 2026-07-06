"""Unit tests for the ProviderRegistry - the mechanism that lets provider
plugins (plugins/providers/*) offer adapters without server.py hardcoding
imports (architecture-design-phase1-v3.md §3).
"""

import pytest

from media_platform.domain.errors import ConfigurationError
from media_platform.kernel.provider_registry import ProviderRegistry


def test_register_then_get_calls_factory():
    registry = ProviderRegistry()
    registry.register("search", "fake", lambda: "a fake search provider")
    assert registry.get("search", "fake") == "a fake search provider"


def test_get_unregistered_raises_with_helpful_message():
    registry = ProviderRegistry()
    registry.register("search", "fake", lambda: object())
    with pytest.raises(ConfigurationError, match="fake"):
        registry.get("search", "does-not-exist")


def test_duplicate_registration_raises():
    registry = ProviderRegistry()
    registry.register("search", "fake", lambda: object())
    with pytest.raises(ConfigurationError):
        registry.register("search", "fake", lambda: object())


def test_available_lists_names_for_a_port_only():
    registry = ProviderRegistry()
    registry.register("search", "a", lambda: object())
    registry.register("search", "b", lambda: object())
    registry.register("storage", "c", lambda: object())
    assert registry.available("search") == ["a", "b"]
    assert registry.available("storage") == ["c"]
