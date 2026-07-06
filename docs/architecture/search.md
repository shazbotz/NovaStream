# Search

Port: `SearchProvider` in `domain/interfaces.py`. Application code never
talks to a search backend directly - only through this interface, via
`CatalogService`.

## Why a native Mongo text index is the Phase 3 default

The reference bots matched filenames with an infix regex
(`re.escape(term)` joined by `.*`) - a full collection scan that no index
can accelerate. A MongoDB `$text` index is tokenized and stemmed and
usable by the query planner, on any tier including free, with zero extra
services to run - see `docs/design-log/architecture-design-phase1.md` §1.

**Built:** `mongo_text` (`plugins/providers/search_mongo_text/`), select
via `SEARCH_PROVIDER=mongo_text`. Not yet run against a live MongoDB
instance in this codebase's own testing - see the adapter's module
docstring for exactly what is and isn't verified.

## Growing beyond it

`suggest()` exists on the interface from day one even though the Mongo
adapter implements it naively (prefix query) - it's the seam where
autocomplete, fuzzy matching, typo tolerance, synonyms, and phonetic
matching land later, in a new adapter (Atlas Search, Meilisearch,
Typesense, Elasticsearch), with zero `CatalogService` changes.

## Why this is a separate port from persistence

See `docs/architecture/storage.md` and
`docs/design-log/architecture-design-phase1-v3.md` §1 - the search index
is a derived, denormalized view of the catalog, which may live in a
different system than the system of record.
