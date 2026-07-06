# Design log

The architecture documents in this directory are kept in the order they
were produced, as a record of *why* the design ended up the way it did -
each one supersedes specific parts of the one before it, not the whole
thing. For the current-state design, read `docs/architecture/*.md`
instead; come here when you want the reasoning behind a specific
decision, or a design alternative that was considered and rejected.

1. `architecture-design-phase1.md` - initial audit of the four reference
   repositories and the first architecture proposal (Koyeb free-tier
   constraints, streaming/search/caching design).
2. `architecture-design-phase1-v2.md` - adds the plugin kernel and the
   Search/Storage/Streaming port interfaces.
3. `architecture-design-phase1-v3.md` - resolves a naming collision
   between two different "StorageProvider" concepts, adds the
   Database/Auth provider ports, and generalizes the plugin system to
   cover adapters as well as features.
4. `open-source-project-structure.md` - repository scaffolding, project
   identity/branding placeholders, credit system, documentation set,
   tooling, and the (still open) license decision.
