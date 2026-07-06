"""Kernel: the plugin runtime and its registries.

Everything a plugin can register into (commands, callbacks, API routes,
scheduled jobs, settings, models) plus the plugin loader itself. The
kernel depends on `services` and `domain`, and is depended on by
`plugins` - see architecture-design-phase1-v3.md §1 for the full
dependency-direction rule.
"""
