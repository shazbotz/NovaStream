"""Application services: thin orchestration over the domain interfaces.

Each service composes one or more ports (SearchProvider, Repository,
StreamingService, ...) into a task-shaped operation that plugins call
through `PluginContext.services`. This is also the seam future AI plugins
build on - see architecture-design-phase1-v2.md §4.

Deliberately free of feature-specific business logic in this bootstrap
phase (ranking, ingestion parsing, retry/backoff tuning) - that lands in
Phase 3 alongside the real provider adapters and feature plugins that need
it. What exists here is the wiring: correct constructors, correct method
shapes, nothing that fabricates behavior a real backend hasn't earned yet.
"""
