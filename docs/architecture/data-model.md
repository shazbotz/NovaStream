# Data model

Domain models live in `src/media_platform/domain/models.py` - plain,
frozen dataclasses, no ORM/ODM coupling (so they're identical regardless
of which `DatabaseProvider` is active).

| Model | Purpose |
|---|---|
| `CatalogItem` | A media file: title, file metadata, `StorageRef`, language/quality/codec/release_type/year/season/episode/genres |
| `SearchQuery` / `SearchResult` / `SearchHit` | Transport-agnostic search request/response |
| `StorageRef` | Opaque, provider-tagged pointer to file bytes |
| `PlaybackURL` | Signed, expiring playback URL |
| `WatchProgress` | Continue-watching state, keyed `user_id:media_id` |
| `FeatureFlag` | Global default + scoped overrides |
| `Credentials` / `AuthenticatedPrincipal` | Transport-specific proof of identity in, uniform principal out |
| `MetadataResult` | Title/year/poster/rating/genres from a metadata provider |
| `MemberStatus` | Telegram chat-membership status |

`codec`, `release_type`, `year`, and `genres` were added in Phase 3
specifically to support catalog variant grouping and genre browsing (see
`plugins/features/catalog_search/grouping.py` and
`plugins/features/genre_browsing/`) - all optional/default-empty, so
existing `CatalogItem` data and callers are unaffected.

Parsing language/quality/season/episode happens once, at index time (a
future `catalog_search` feature plugin's ingestion pipeline) - not on
every search request. See
`docs/design-log/architecture-design-phase1.md` §5.
