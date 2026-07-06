"""Provider plugins: each registers one adapter implementation for a port
(search, storage, database, auth, metadata, streaming, telegram).

The bootstrap phase ships only 'null'/'memory' adapters - safe defaults
that let the application start with zero external credentials configured.
Real adapters (mongo, telegram, s3, meilisearch, ...) are added here in
later phases, each as its own sibling directory, with zero changes to
core code.
"""
