# Auth

Port: `AuthProvider` - `authenticate(credentials) -> AuthenticatedPrincipal
| None`. Every route and service consumes the same `AuthenticatedPrincipal`
regardless of which adapter produced it, which is what lets different
client types (Bot, Mini App, future Web Dashboard/Desktop/Mobile)
authenticate differently while `services/*` stays transport-agnostic.

Bootstrap adapter: `null` - always returns `None` (nobody is
authenticated). Phase 3+: `telegram_init_data` (validates the Mini App's
signed `initData`), later `api_key` / `oauth` for other client types.
