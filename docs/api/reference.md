# API reference

The JSON API surface is built entirely from routes that feature plugins
register via `ctx.api.get(...)` / `ctx.api.post(...)` -
`kernel/api_router.py` has no routes of its own beyond what `server.py`
adds directly (`/healthz`). Handlers take an `ApiRequest` and return an
`ApiResponse` (see `kernel/api_router.py`) - `server.py` is the only
place that adapts these to/from real aiohttp requests/responses, and the
only place that maps errors to HTTP status codes:

| Raised by a handler | HTTP status |
|---|---|
| `ValidationError` | 400 |
| `AuthenticationError` | 401 |
| `PermissionError_` | 403 |
| `NotFoundError` | 404 |
| `ProviderError` | 502 |
| `ConfigurationError` | 500 |
| anything else (a bug) | 500, logged server-side, details not exposed to the caller |

## Always available

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | Process/provider/plugin health check |

## catalog_search (Phase 3)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/search` | none | Search the catalog, grouped by title+year. Query params: `q` (text), `offset` (default 0), `limit` (default 10, capped at 50). |
| POST | `/api/media` | required | Register a media item. Body: `id`, `title`, `file_name`, `file_size`, `mime_type`, `storage_ref: {provider, payload}`, optionally `caption`, `language`, `quality`, `codec`, `release_type`, `year`, `season`, `episode`, `genres: [string]`. |

`GET /api/search` response shape (variant-grouped - see
`docs/architecture/data-model.md`):
```json
{
  "results": [
    {
      "title": "The Matrix",
      "year": 1999,
      "variant_count": 2,
      "languages": ["en", "hi"],
      "qualities": ["1080p", "720p"],
      "variants": [
        {"media_id": "...", "language": "en", "quality": "1080p", "codec": "x264", "release_type": "BluRay", "file_size": 2147483648},
        {"media_id": "...", "language": "hi", "quality": "720p", "codec": "HEVC", "release_type": "WEB-DL", "file_size": 900000000}
      ]
    }
  ],
  "total": 1,
  "has_more": false
}
```
`total` counts raw search hits (pre-grouping), not the number of groups -
see `SearchResult`'s docstring for why it's exact only when `has_more` is
`false`. `variant_count == 1` is the signal a client should skip a
language/quality selection step and go straight to that variant - see
`plugins/features/catalog_search/grouping.py`.

Note: with the default bootstrap providers (`AUTH_PROVIDER=null`),
`POST /api/media` always returns 401 - the null adapter never
authenticates anyone. Configure a real `AuthProvider` to use this route.

## continue_watching

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/continue-watching` | required | The authenticated caller's in-progress items. |
| POST | `/api/watch-progress` | required | Record playback position. Body: `media_id`, `position_seconds`, optionally `duration_seconds`. |

`user_id` always comes from the authenticated principal, never from the
request - see the plugin's docstring for why that's a deliberate security
choice, not an oversight.

## genre_browsing

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/genres/{genre}` | none | Items tagged with the given genre. Query params: `offset`, `limit` (capped at 50). |

Listing all distinct genre names isn't implemented yet - see the plugin's
docstring for why.

## streaming

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/stream-token/{media_id}` | required | Issue a signed, expiring playback URL for in-app streaming. |
| GET | `/api/download-token/{media_id}` | required | Same as above, tagged (`&dl=1`) so the raw stream handler sends `Content-Disposition: attachment`. |

Response shape (both routes):
```json
{
  "url": "https://your-deployment.example.com/stream/{media_id}?exp=1719999999&sig=...&u=42",
  "expires_at": "2026-07-07T18:00:00+00:00",
  "file_name": "interstellar.1080p.mkv",
  "file_size": 2200000000,
  "mime_type": "video/x-matroska"
}
```

`url` is only valid until `expires_at` and only for the user_id baked
into its signature - see `services/stream_tokens.py`.

## Raw `/stream/{media_id}` (not through `ApiRouter`)

Registered directly on the aiohttp app by `server.py`, next to
`/healthz` - not a JSON route, so it's not in the table above. Takes
`?exp=...&sig=...&u=...` (and optionally `&dl=1`) as minted by
`/api/stream-token` or `/api/download-token`, verifies the signature and
expiry, then streams bytes from whichever `StorageProvider` is
configured, honoring `Range` requests (`206 Partial Content` /
`416 Range Not Satisfiable`) so browser/Mini-App video players can seek.
Returns `403` for an invalid/expired/tampered token, `404` if the
`media_id` doesn't exist, `502` if the storage backend read fails. See
`docs/architecture/streaming.md`.
