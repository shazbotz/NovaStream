# Credits

## Design Inspiration

Nova Stream was designed using widely adopted software architecture principles
and engineering patterns commonly found in modern distributed systems and
high-performance Telegram applications.

The project was implemented from scratch with its own architecture, plugin
system, domain model, APIs, and user experience. While general engineering
approaches were studied from public resources, no project's source code or
overall architecture was copied.

Some engineering concepts adopted include:

- Concurrent producer/consumer indexing pipelines
- HTTP range-based media streaming
- Background task scheduling with bounded concurrency
- Plugin-based modular architecture
- Dependency injection and service abstraction
- Scalable caching and asynchronous processing
- Telegram-native administrative workflows

For more information about the architectural decisions, see:

- `docs/architecture/overview.md`
- `docs/design-log/`

---

# Third-Party Libraries

Nova Stream is built using several excellent open-source projects.

- aiohttp — Async HTTP server
- Motor — Async MongoDB driver
- Pyrogram / Kurigram — Telegram MTProto framework
- Pydantic — Configuration and validation
- Additional dependencies are listed in `pyproject.toml`.

---

# Contributors

Nova Stream is currently maintained by its author.

Community contributions are welcome through pull requests, bug reports,
feature requests, and documentation improvements.

---

# Acknowledgements

Special thanks to the open-source community for providing the tools,
libraries, documentation, and educational resources that made this project
possible.
