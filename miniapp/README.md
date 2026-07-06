# Mini App

React + Vite + TypeScript + Tailwind frontend for the Telegram Mini App,
per the plan in `docs/design-log/architecture-design-phase1.md` §4.4.

## Status

Implemented this pass: Search, Browse (genre grid + per-genre list),
Media Details (variant selection), and a Player page, wired together by
a small in-memory navigation stack - no routing/build/data-fetching
library beyond React itself and the `fetch` API.

**Not run in the environment this was built in** - no network access to
`npm install` any package (registry returns 403), so nothing here has
been through `vite build`, `tsc --noEmit`, or a dev server, only manual
review. Node.js itself *is* available in that environment (unlike an
earlier pass, which is why this used to say Node wasn't available), so
running the commands below in a normal, network-connected environment is
the first thing to do before deploying this.

```bash
cd miniapp
npm install
npm run typecheck   # tsc --noEmit
npm run build        # tsc --noEmit && vite build -> dist/
npm run dev           # local dev server, http://localhost:5173
```

## Stack

- React 18 + Vite + TypeScript, Tailwind for styling.
- Deployed as a static bundle to a CDN/static host (Cloudflare Pages,
  Vercel, GitHub Pages) - **not** served from the same instance as the
  bot/API, to keep the 512MB Koyeb instance's resources for the bot and
  streaming.
- Talks to the backend's JSON API (`../docs/api/reference.md`) over
  HTTPS - see `src/lib/api-client.ts`.
- Authenticates via Telegram's `initData` (`src/lib/telegram.ts`), sent
  as a Bearer token - see `../docs/architecture/auth.md`. The backend's
  bootstrap `AUTH_PROVIDER=null` adapter never authenticates anyone, so
  every authenticated route (stream/download tokens, continue watching)
  will 401 against the bootstrap backend until a real `AuthProvider` is
  configured; the Mini App's job here is just to send the header, not to
  verify anything itself.
- Player: a native `<video>` element, not a third-party player library -
  see `src/player/VideoPlayer.tsx`'s docstring for why that's a
  deliberate, revisitable choice rather than an oversight.

## Directory layout

```
src/
  types.ts            API response shapes, hand-kept in sync with docs/api/reference.md
  lib/
    api-client.ts     fetch wrapper for every backend route this app calls
    telegram.ts       window.Telegram.WebApp wrapper (initData, back button, haptics)
    navigation.ts     in-memory navigation stack (see App.tsx)
  components/         shared UI (Header, BottomNav, MediaCard, loading/error states)
  pages/              SearchPage, BrowsePage, MediaDetailsPage, PlayerPage
  player/             VideoPlayer
  App.tsx             wires navigation state to pages
  main.tsx            React entry point
```

## Deliberately not built this pass

- **Continue Watching / Downloads / Watchlist / Settings / a hamburger
  menu** (screens 6-10 in the reference mockup) - the prompt that started
  this pass scoped the Mini App to "Search page, Browse page, Media
  Details page, Video Player, Navigation state, React frontend"
  specifically; the backend for Continue Watching already exists
  (`GET /api/continue-watching`, used by `PlayerPage` to resume
  playback) and `PlayerPage` reports progress to it, but there's no
  dedicated "Continue Watching" *screen* yet. Adding one is a new page
  plus a nav-stack entry, following the exact pattern `BrowsePage`
  already establishes - no new architecture needed.
- Watchlist/Favorites, a Downloads tab with its own state, and Settings
  have no backend routes yet at all (see the main `ROADMAP.md`) - building
  the screens without the API they'd call would just be a mock.
- A `GET /api/genres` (list all distinct genre names) route doesn't
  exist yet (see `genre_browsing/plugin.py`'s docstring), so the Browse
  page's genre grid uses a fixed client-side list
  (`api-client.ts`'s `BROWSE_GENRES`) rather than fetching one.

## Theming

Not yet decided beyond the dark palette already in `tailwind.config.js` -
see `../docs/guides/theme-development.md`.
