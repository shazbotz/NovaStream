"""Unit tests for FeatureFlagService's resolution order (env kill-switch
-> user -> chat/group -> global) - see architecture-design-phase1-v2.md
§2.5. Uses the in-memory Repository adapter as a fake; no real database.
"""

import os

import pytest

from media_platform.cache.ttl_cache import TTLCache
from media_platform.domain.models import FlagScope
from media_platform.plugins.providers.database_memory.provider import InMemoryDatabaseProvider
from media_platform.services.feature_flags import FeatureFlagService


@pytest.fixture
def flags():
    db = InMemoryDatabaseProvider()
    cache: TTLCache = TTLCache(max_size=64, ttl_seconds=60)
    return FeatureFlagService(repository=db.repository("feature_flags"), cache=cache)


async def test_unknown_feature_defaults_to_disabled(flags):
    assert await flags.is_enabled("nope") is False


async def test_global_default_applies_to_everyone(flags):
    await flags.set("mini_app", True, scope=FlagScope.GLOBAL)
    assert await flags.is_enabled("mini_app") is True
    assert await flags.is_enabled("mini_app", user_id=1) is True


async def test_user_override_wins_over_global_default(flags):
    await flags.set("mini_app", True, scope=FlagScope.GLOBAL)
    await flags.set("mini_app", False, scope=FlagScope.USER, scope_id=42)
    assert await flags.is_enabled("mini_app", user_id=42) is False
    assert await flags.is_enabled("mini_app", user_id=999) is True


async def test_scoped_set_requires_scope_id(flags):
    from media_platform.domain.errors import ValidationError

    with pytest.raises(ValidationError):
        await flags.set("mini_app", True, scope=FlagScope.USER)


async def test_env_kill_switch_overrides_everything(flags, monkeypatch):
    await flags.set("mini_app", True, scope=FlagScope.GLOBAL)
    monkeypatch.setenv("FEATURE_MINI_APP_DISABLED", "true")
    assert await flags.is_enabled("mini_app") is False
