# Streaming

Port: `StreamingService`. This is the *entire* surface the Bot and Mini
App are allowed to know about - `get_playback_url(media_id, user_id) ->
PlaybackURL`. Neither ever sees a `StorageRef`, a worker pool, or a chunk
size.

## Why this buys a future language/deployment change for free

The interface is plain data in, plain data out - no shared connections or
in-process objects cross it. Swapping the in-process implementation for
an HTTP call to a standalone service (Python, Go, Rust - doesn't matter)
is a pure adapter swap, exactly like the other ports. See
`docs/design-log/architecture-design-phase1-v2.md` §2.3.

## Bootstrap adapter

`null` - raises `ProviderError` on `get_playback_url()`. There is no
streaming engine wired up until a real `StorageProvider` exists to serve
bytes from.

## Real adapters (implemented this pass)

- **`streaming_signed`** (`STREAMING_PROVIDER=signed`) - issues
  HMAC-SHA256-signed, expiring playback URLs pointing at the raw
  `/stream/{media_id}` HTTP handler registered directly by `server.py`.
  Signing logic lives in `services/stream_tokens.py` so the same code
  signs (this adapter) and verifies (the `/stream` handler). Requires
  `STREAM_SECRET`; `PUBLIC_BASE_URL` and `STREAM_URL_EXPIRY_SECONDS` are
  optional. `revoke()` is a documented no-op - see the plugin's
  docstring for why a stateless signed URL can't be revoked before its
  own expiry, and what a future revocation list would need.

- **`storage_telegram`** (`STORAGE_PROVIDER=telegram`) - the
  `StorageProvider` a deployment pairs with `streaming_signed` to
  actually serve bytes: reads directly from the Telegram chat/message a
  file lives in (`StorageRef(provider="telegram", payload={"chat_id":
  ..., "message_id": ...})`), via a dedicated, lazily-connecting pool of
  kurigram clients (`plugins/providers/storage_telegram/client.py`) kept
  separate from the bot-core `TelegramGateway` so streaming load can
  never starve the bot's ability to answer commands. Round-robins across
  `STREAM_WORKER_TOKENS` if set, otherwise falls back to the single
  `BOT_TOKEN`. **Not executable-verified** - no `kurigram` install or
  live credentials in the environment this was built in; same caveat as
  `telegram_kurigram`. Checked with `python -m py_compile` and manual
  review only.

The raw `/stream/{media_id}` handler (not through `ApiRouter` - see
`docs/api/reference.md`) is what actually reads from `StorageProvider`
and streams bytes to the client, with `Range` header support
(`services/range_parsing.py`, unit tested) so players can seek and so
downloads resume. `PlaybackService`/`StreamingService` never touch
`StorageProvider` directly or vice versa - the only thing connecting a
signed URL to actual bytes is the `media_id` both ends look up
independently in the catalog.

## Offline download

Not a separate storage/queueing mechanism - "download" is the same
signed URL as streaming, with `&dl=1` appended (added by
`/api/download-token/{id}`) so the `/stream` handler sends
`Content-Disposition: attachment` instead of an inline response. A
device's own OS/browser download manager handles the actual "save for
offline playback" part, same as any other website's download link - the
Mini App does not need its own download manager, queue, or storage
quota logic for this to work.

## Not yet built

A worker-pool-wide adaptive block-size/prefetch strategy beyond
kurigram's own internal chunking, and a server-side stream-token
revocation list - both called out above and in
`docs/design-log/architecture-design-phase1.md` §4.3 as later
refinements on top of what's here now, not blockers for streaming/download
to work.
