"""Shared support code for the Mongo-family provider plugins
(database_mongo, search_mongo_text) - NOT itself a plugin (no `plugin.py`
here, so `kernel/plugin_manager.py`'s discovery correctly skips it).

Exists specifically so `database_mongo` and `search_mongo_text` don't
import from each other directly, which would violate "plugins never
import another plugin's module" (docs/guides/plugin-development.md) -
both legitimately need the same CatalogItem<->Mongo-document shape
because they operate on the same `media` collection by design (see
docs/architecture/search.md), so that shared knowledge lives here
instead of one plugin reaching into the other.
"""
