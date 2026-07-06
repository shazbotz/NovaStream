"""Feature-flag resolution: env kill-switch -> user -> chat/group -> global.

See architecture-design-phase1-v2.md §2.5 for the resolution order and
architecture-design-phase1-v3.md §6 for the flag inventory this serves.
"""

from __future__ import annotations

import os

from media_platform.domain.errors import ValidationError
from media_platform.domain.interfaces import Repository
from media_platform.domain.models import FeatureFlag, FlagScope
from media_platform.cache.ttl_cache import TTLCache


class FeatureFlagService:
    def __init__(
        self, repository: Repository[FeatureFlag], cache: TTLCache[str, FeatureFlag]
    ) -> None:
        self._repository = repository
        self._cache = cache

    async def is_enabled(
        self,
        feature: str,
        *,
        user_id: int | None = None,
        chat_id: int | None = None,
        group_id: int | None = None,
    ) -> bool:
        kill_switch = os.environ.get(f"FEATURE_{feature.upper()}_DISABLED")
        if kill_switch and kill_switch.strip().lower() in ("1", "true", "yes", "on"):
            return False

        flag = await self.get(feature)
        if flag is None:
            return False

        for scope, scoped_id, enabled in flag.overrides:
            if scope is FlagScope.USER and user_id is not None and scoped_id == user_id:
                return enabled
            if scope is FlagScope.CHAT and chat_id is not None and scoped_id == chat_id:
                return enabled
            if scope is FlagScope.GROUP and group_id is not None and scoped_id == group_id:
                return enabled

        return flag.global_default

    async def set(
        self,
        feature: str,
        enabled: bool,
        *,
        scope: FlagScope,
        scope_id: int | None = None,
    ) -> None:
        flag = await self.get(feature) or FeatureFlag(name=feature)
        if scope is FlagScope.GLOBAL:
            flag = FeatureFlag(
                name=feature, global_default=enabled, overrides=flag.overrides
            )
        else:
            if scope_id is None:
                raise ValidationError(f"scope_id is required for scope={scope}")
            overrides = tuple(
                o for o in flag.overrides if not (o[0] == scope and o[1] == scope_id)
            )
            overrides = overrides + ((scope, scope_id, enabled),)
            flag = FeatureFlag(
                name=feature, global_default=flag.global_default, overrides=overrides
            )
        await self._repository.save(flag)
        self._cache.delete(feature)

    async def get(self, feature: str) -> FeatureFlag | None:
        cached = self._cache.get(feature)
        if cached is not None:
            return cached
        flag = await self._repository.get(feature)
        if flag is not None:
            self._cache.set(feature, flag)
        return flag
