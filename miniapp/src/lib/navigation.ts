// A deliberately small, in-memory navigation stack instead of pulling in
// react-router - this app has five screens total (see README.md) and a
// Telegram Mini App is a single WebView, not a multi-page site, so
// there's no URL bar for deep-linking to preserve. Browser back/gesture
// is wired to Telegram's own `BackButton` (see `telegram.ts`), not to
// `history`/URL state.

export type Route =
  | { name: "search" }
  | { name: "browse" }
  | { name: "genre"; genre: string }
  | { name: "details"; title: string; year: number | null }
  | { name: "player"; mediaId: string; title: string };

export interface NavigationState {
  stack: Route[];
}

export type NavigationAction =
  | { type: "push"; route: Route }
  | { type: "back" }
  | { type: "reset"; route: Route };

export function navigationReducer(state: NavigationState, action: NavigationAction): NavigationState {
  switch (action.type) {
    case "push":
      return { stack: [...state.stack, action.route] };
    case "back":
      return state.stack.length > 1 ? { stack: state.stack.slice(0, -1) } : state;
    case "reset":
      return { stack: [action.route] };
    default:
      return state;
  }
}

export const initialNavigationState: NavigationState = { stack: [{ name: "search" }] };
