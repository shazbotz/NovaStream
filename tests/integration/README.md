# Integration tests

Empty in the bootstrap phase on purpose: there are no real adapters
(Mongo, Telegram, S3, ...) yet to integrate with - only the null/in-memory
bootstrap adapters, which are already covered by `tests/unit`.

Once Phase 3 adds a real `DatabaseProvider` (Mongo/Postgres) or
`TelegramGateway` (kurigram-backed) adapter, its tests go here, run
against disposable real infrastructure (a test database, a test bot), and
are wired into CI on a schedule rather than every commit - see
`docs/guides/coding-standards.md` for the fast/slow test split.
