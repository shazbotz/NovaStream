# Open Source Project Structure & Governance (Phase 1)

Companion to `architecture-design-phase1-v3.md`. That document is the runtime architecture; this one is everything about the repository being a professionally maintained, public, contributor-friendly project from day one — items 1, 2, 3, 11, and the process parts of 12/13 from your latest requirements.

---

## 1. Repository scaffolding

```
media-platform/
  README.md
  LICENSE
  CONTRIBUTING.md
  CODE_OF_CONDUCT.md
  CHANGELOG.md
  SECURITY.md                 # how to report vulnerabilities privately
  PROJECT.toml                 # single source of identity/branding metadata, see §2
  CREDITS.md
  .github/
    ISSUE_TEMPLATE/
      bug_report.md
      feature_request.md
    PULL_REQUEST_TEMPLATE.md
    workflows/
      ci.yml                   # lint + type-check + unit tests, every PR
      release.yml               # build + tag on version bump
  docs/                         # see §4
  (the app/ tree from architecture-design-phase1-v3.md)
```

This is the same shape as most mature Python OSS repos (Home Assistant, Sanic, Litestar, etc.) — nothing exotic, which is itself the point: a contributor who's used GitHub before should recognize where everything is without reading a guide first.

---

## 2. Project identity — no hardcoded personal information anywhere

Single source of truth, one file, referenced everywhere else instead of repeated:

```toml
# PROJECT.toml
[project]
name = ""
tagline = ""
description = ""
license = ""              # filled once §7 is decided
repository_url = ""

[people]
author = ""
maintainer = ""
github_username = ""
telegram_username = ""

[links]
website = ""
docs_url = ""
support_chat = ""

[credits]
inspirations = []          # see §3 — technique-level, not names
upstream_projects = []
special_thanks = []
```

- `README.md`, `LICENSE` header, `docs/`, and the Mini App footer all reference these fields as `{{project.name}}`-style tokens rather than containing literal text. For Phase 1, simplest-thing-that-works: fill the tokens by hand when you're ready to publish (a five-minute find-and-replace). A small `scripts/render_templates.py` that does the substitution automatically is a reasonable Phase 2+ nicety, not a Phase 1 requirement — no need to stand up a templating pipeline before there's anything to template.
- Application code (bot handlers, services, plugins) never reads `PROJECT.toml` — it's a docs/branding concern only, kept out of runtime config (`config.py`) so branding changes can never accidentally affect behavior.

---

## 3. Credit system

`CREDITS.md`, referenced from the README:

```markdown
## Inspirations
This project's architecture draws on patterns studied from several
open-source Telegram bot projects, reworked from scratch:
- Producer/consumer bulk-indexing pipelines
- HTTP range-request streaming with concurrent block prefetching
- In-Telegram admin panel UX

## Upstream Projects
- kurigram — Telegram MTProto client library
- aiohttp — async HTTP server
- motor — async MongoDB driver
- Vidstack — web media player

## Contributors
(populated as people contribute)

## Special Thanks
{{project.credits.special_thanks}}
```

Note on how the "Inspirations" section is worded: it credits the **techniques**, not specific project names/branding. That's a deliberate choice consistent with what we agreed earlier in this design process — this project is a from-scratch redesign, not a fork, and the reference material it studied included pieces (monetization/growth/evasion mechanics) that aren't part of this project at all. Crediting a technique ("block-prefetch streaming") is accurate and generous; crediting a specific piracy-associated bot brand by name in a public OSS project's credits isn't something I'll draft. If you want to name specific upstream *libraries* (kurigram, aiohttp, etc. — all legitimate, unaffiliated infrastructure) that's normal and already included above.

---

## 4. Documentation set

```
docs/
  architecture/
    overview.md              # system diagram, ports & adapters + plugin kernel, why
    search.md  storage.md  streaming.md  auth.md   # one page per port, adapters listed
    feature-flags.md
    data-model.md
  guides/
    plugin-development.md     # how to write a feature plugin and a provider plugin
    theme-development.md      # Mini App theming — see note below
    contributing.md
    coding-standards.md
    deployment.md             # Koyeb free tier, env vars, first-run checklist
    performance.md            # the resource budget from v1 §2/§7, what to watch
  api/
    reference.md              # Mini App JSON API, kept in sync with kernel/api_router.py
```

**Plain Markdown in `docs/`, no static-site generator, for Phase 1.** It's portable, diffable, and needs zero build tooling — you can add MkDocs Material or Docusaurus later for a hosted docs site by pointing it at the same files, without restructuring anything now.

**Theme development guide** — your requirements mention this but nothing earlier in this design specified an actual theming system for the Mini App. Two honest options rather than me assuming one:
- *Minimal:* the Mini App already inherits Telegram's light/dark theme via the WebApp SDK's theme params (background/text/button colors) — "theming" is just consistently using those CSS variables, which is close to zero extra architecture.
- *Full:* a proper theme system (swappable color tokens/layouts beyond what Telegram provides, maybe user-selectable). That's a real feature with its own design work, not a byproduct of anything built so far.
I'd default to the minimal version for Phase 1 and treat a full theme system as a future plugin-adjacent feature — flagging as an open decision (§6) rather than guessing which you meant.

---

## 5. Coding standards & tooling

| Concern | Tool | Why |
|---|---|---|
| Formatting + linting | `ruff` | One fast tool instead of black+isort+flake8 separately; less config, less CI time |
| Type checking | `mypy` (or `pyright`) | The Protocol-based interfaces in v2/v3 are exactly where type checking earns its keep — a wrong adapter shape fails at CI, not at runtime |
| Tests | `pytest` + `pytest-asyncio` | Standard for async Python |
| Pre-commit | `pre-commit` running ruff + mypy | Catches issues before they reach CI |
| Commit convention | Conventional Commits | Enables automated `CHANGELOG.md` generation |
| CI | GitHub Actions: lint → type-check → unit tests, on every PR; integration tests on a schedule | Matches the fast/slow test split from v3 §5 |

`pyproject.toml` becomes the single config file for the project's own metadata (name, version, dependencies) *as a Python package* — distinct from `PROJECT.toml`'s branding metadata (§2). Keeping these separate means a packaging tool never needs to parse branding fields, and branding edits never touch dependency/version data.

---

## 6. Versioning & release process

- Semantic versioning (`MAJOR.MINOR.PATCH`) from the first tagged release.
- `CHANGELOG.md` generated from Conventional Commit history, one section per release.
- A version bump + tag triggers `.github/workflows/release.yml` to build and (optionally) publish a Docker image.
- Plugin API stability: since third parties are meant to write plugins (item 8), the `Plugin`/`PluginContext`/port interfaces in `domain/` are the platform's **public API surface** — breaking changes to them are MAJOR-version events, documented in the changelog under a dedicated "Plugin API changes" heading so plugin authors can find them without reading the whole log.

---

## 7. Open decision: license

Not defaulting this silently — it's a legal and strategic choice, not just an engineering one.

| Option | What it means here |
|---|---|
| **MIT / Apache-2.0** | Maximally permissive — anyone can fork, embed, or run this as a closed/commercial service without contributing back. Fits "reusable framework others build upon" (your item 13 wording) most literally. |
| **AGPL-3.0** | Anyone running a *modified* version as a network service must publish their modifications. Common choice for self-hosted server software specifically to prevent someone taking the project, closing the source, and selling it as a SaaS without contributing back. It's also what the reference ecosystem's original license (EvaMaria) used, for context, not as a reason to pick it. |
| **BSL / source-available** | Delays full open-source rights for a period (e.g. converts to Apache-2.0 after N years) — used by some commercial-open-core projects. Adds complexity most personal/community projects don't need. |

If the goal is maximum adoption and contribution as a framework, MIT/Apache-2.0 is the more common fit. If the goal is "stay open, prevent someone else profiting from a closed fork," AGPL-3.0 is the more common fit. Tell me which matters more and I'll finalize `LICENSE` and the corresponding line in `PROJECT.toml`.

---

## 8. Open decisions added by this document

11. Theme system for the Mini App: minimal (inherit Telegram theme params) or a full custom theming layer?
12. License: MIT/Apache-2.0 vs AGPL-3.0 vs something else (§7)?
13. Docker image publishing on release: yes (and to where — GHCR, Docker Hub) or not for Phase 1?

(Continuing the numbering from `architecture-design-phase1-v3.md` §8, items 1–10.)
