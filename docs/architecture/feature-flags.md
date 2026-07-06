# Feature flags

Port: `FeatureFlags`, implemented by `services/feature_flags.py`
(`FeatureFlagService`) using a `Repository` + the bounded `TTLCache`.

## Resolution order (most specific wins)

1. Environment kill-switch: `FEATURE_<NAME>_DISABLED=true` - forces a
   feature off platform-wide regardless of stored state, for incident
   response.
2. User-scoped override
3. Chat/group-scoped override
4. Global default

## Load-time vs. runtime gating

- A plugin listed in `PLUGINS_DISABLED` is **never imported** - zero RAM,
  zero startup cost. For heavy/optional plugins.
- A loaded plugin that should be toggle-able per chat/group/user checks
  `FeatureFlags.is_enabled()` at the top of its handler - a cached lookup,
  not a database round trip.

See `docs/design-log/architecture-design-phase1-v3.md` §6 for the current
flag inventory.
