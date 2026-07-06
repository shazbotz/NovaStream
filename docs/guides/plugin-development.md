# Plugin development guide

There are two kinds of plugin. Both are discovered automatically at
startup - nothing outside `plugins/` ever imports a specific plugin
module by name.

## Feature plugin

Lives under `src/media_platform/plugins/features/<your_plugin>/`, with an
`__init__.py` and a `plugin.py` exposing a module-level `PLUGIN`. The
example below is illustrative - for a real, fully unit-tested
implementation of this exact pattern, read
`src/media_platform/plugins/features/catalog_search/plugin.py` and its
tests in `tests/unit/test_catalog_search_plugin.py`.

```python
# plugins/features/hello/plugin.py
from typing import Awaitable, Callable

from media_platform.kernel.api_router import ApiRequest, ApiResponse
from media_platform.kernel.plugin import PluginContext

Reply = Callable[[str], Awaitable[None]]


class HelloPlugin:
    name = "feature.hello"
    version = "0.1.0"
    requires: tuple[str, ...] = ()  # other plugin names that must load first

    def register(self, ctx: PluginContext) -> None:
        # Bind exactly what you need from ctx.services - not the whole
        # context - so it's obvious what this plugin actually depends on.
        self._catalog = ctx.services.catalog

        ctx.commands.register("hello", self.cmd_hello)
        ctx.callbacks.register("hello:", self.cb_hello)
        ctx.api.get("/hello", self.api_hello)
        ctx.scheduler.every(3600, "hello.ping", self.job_ping)
        ctx.settings.register("hello.greeting", default="Hi!", description="Greeting text")

    # Bot transport: plain args in, a `reply` callback out - never a
    # Telegram-specific message object. See plugins/features/catalog_search
    # for a fully worked, tested example of this pattern (its `cmd_search`).
    async def cmd_hello(self, args: str, reply: Reply) -> None:
        await reply("Hi!")

    async def cb_hello(self, query, ctx: PluginContext) -> None: ...

    # HTTP transport: takes an ApiRequest, returns an ApiResponse - never
    # an aiohttp Request/Response. server.py is the only place aiohttp
    # types exist; this is what keeps that true, not just documented.
    async def api_hello(self, request: ApiRequest) -> ApiResponse:
        return ApiResponse(body={"message": "Hi!"})

    async def job_ping(self) -> None: ...


PLUGIN = HelloPlugin()
```

Rules:
- Never import `aiohttp`, a Telegram client library, or a database driver
  directly - everything you need is reachable through `ctx`.
- Never import another plugin's module directly. If two provider plugins
  legitimately need to share code (e.g. two Mongo-backed adapters sharing
  document (de)serialization), put the shared code in a non-plugin
  support package (no `plugin.py` inside it, so discovery correctly skips
  it) - see `plugins/providers/_mongo_shared/` for a real example.
- Call `ctx.services.*`, never a concrete adapter.
- If your provider plugin's own module imports a third-party dependency
  that isn't installed (e.g. `motor`, `kurigram`), plugin discovery logs
  a warning and skips it rather than crashing the whole application -
  your provider just won't show up in `ProviderRegistry.available(port)`
  until the dependency is installed. Declare it as an optional dependency
  group in `pyproject.toml` (see the `mongo`/`telegram` extras) so users
  know what to install.

## Provider plugin

Lives under `src/media_platform/plugins/providers/<your_provider>/`,
implementing one of the ports in `domain/interfaces.py`:

```python
# plugins/providers/my_search_backend/plugin.py
from media_platform.kernel.plugin import ProviderContext


class MySearchBackendProvider:
    async def index(self, doc): ...
    async def remove(self, doc_id): ...
    async def search(self, query): ...
    async def suggest(self, prefix, limit=10): ...


class MySearchBackendPlugin:
    name = "provider.search.my_backend"
    version = "0.1.0"
    requires: tuple[str, ...] = ()

    def register(self, ctx: ProviderContext) -> None:
        ctx.providers.register("search", "my_backend", MySearchBackendProvider)


PLUGIN = MySearchBackendPlugin()
```

Select it by setting `SEARCH_PROVIDER=my_backend` (or the corresponding
env var for whichever port you implemented) - no other code changes.

If your adapter needs credentials or a connection string, read them from
`ctx.config` (the raw `Settings`) inside the factory function, and raise
`ConfigurationError` there if something required is missing - this
validates lazily, only when your adapter is actually selected, not at
every startup regardless of which provider is configured. See
`src/media_platform/plugins/providers/database_mongo/plugin.py` for a
real example of this pattern.

## Load order

If your plugin depends on another, list it in `requires`. The plugin
manager topologically sorts by this and fails loudly at startup (not at
first use) if a dependency is missing or a cycle exists.

## Testing

Prefer testing against a fake/in-memory implementation of whatever port
your plugin depends on (see `plugins/providers/database_memory/` for an
example of a fully functional in-memory adapter) rather than a real
backend - keeps `tests/unit` fast and dependency-free. Real-backend tests
go in `tests/integration/`.
