# Storage - two different concerns, two different ports

This project has two things that could reasonably be called "storage,"
kept as two separate ports specifically to avoid the ambiguity that
caused a naming collision during design (see
`docs/design-log/architecture-design-phase1-v3.md` §0):

## `StorageProvider` - where file bytes live

Telegram, S3, R2, B2, Google Drive, local disk. Methods: `put`,
`get_range`, `get_metadata`, `delete`. A `StorageRef` (provider-tagged,
opaque payload) is stored on the catalog item instead of a bare Telegram
`file_id` - the catalog doesn't care which shape it holds, and different
items can use different providers simultaneously.

Bootstrap adapter: `null` (raises `ProviderError` - there's nothing to
serve bytes from yet). Planned default: `telegram`, implementing the
concurrent block-prefetch design from
`docs/design-log/architecture-design-phase1.md` §4.3 - **not yet built**;
needs a live bot token to develop against meaningfully, deliberately not
attempted without one. See `ROADMAP.md`.

## `DatabaseProvider` / `Repository` - where structured records live

Catalog metadata, users, watch history, feature flags. One
`DatabaseProvider` per backend (Mongo/Postgres/MySQL/SQLite), each handing
out named `Repository` instances.

Bootstrap adapter: `memory` - fully functional, dict-backed, but
non-persistent (nothing survives a process restart).

Real adapter: `mongo` (motor-based) - implemented, with unit-tested
(de)serialization codecs (`tests/unit/test_mongo_codecs.py`). Not yet run
against a live MongoDB instance in this codebase's own testing (see
`plugins/providers/database_mongo/provider.py`'s docstring) - review
before trusting in production, then move this note once it's been run
for real.

SQLite is supported by the interface but not recommended for concurrent
production use (file-based, effectively single-writer) - fine for local
dev, tests, or a single-user deployment. No `sqlite`/`postgres`/`mysql`
adapter has been written yet.
