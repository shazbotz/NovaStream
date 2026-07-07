# Credits

## Inspirations

This project's architecture draws on engineering patterns studied from several open-source Telegram projects and modern software architecture practices. The implementation was redesigned from scratch around a plugin-based, ports-and-adapters architecture.

The following engineering concepts inspired parts of the implementation:

- Producer/consumer bulk-indexing pipelines with bounded concurrency
- HTTP range-request streaming with concurrent block prefetching
- Semaphore-bounded broadcast fan-out
- Telegram bot administration workflows
- Plugin-based application architecture

These are credited as engineering concepts only. Nova Stream is an original implementation and is not a fork of any existing project.

---

## Open Source Libraries

Nova Stream is built on top of several excellent open-source projects, including:

- aiohttp
- Kurigram
- Motor
- PyMongo
- Python
- React
- Vite

Additional libraries can be found in `pyproject.toml`.

---

## Contributors

Contributions are welcome.

See `CONTRIBUTORS.md` for the complete contributor list.

---

## Created By

**SHAZ BOTS**

Project Lead: **Muhammed Shamil**

GitHub: https://github.com/shazbotz

Telegram: https://t.me/shamil_shaz03

---

## Special Thanks

Thanks to the open-source community and everyone who contributes ideas, bug reports, testing, and improvements to Nova Stream.
