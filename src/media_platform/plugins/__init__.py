"""Plugins live here, one directory per plugin, under either `providers/`
(implements a port, registers via `ctx.providers`) or `features/`
(registers commands/callbacks/routes/jobs, uses `ctx.services`).

Nothing outside `plugins/` imports a specific plugin module by name - the
PluginManager discovers them by scanning these two packages. See
architecture-design-phase1-v3.md §3 and docs/guides/plugin-development.md.
"""
