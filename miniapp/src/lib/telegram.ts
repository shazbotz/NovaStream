// Thin wrapper around the global `window.Telegram.WebApp` object the
// `<script src="https://telegram.org/js/telegram-web-app.js">` tag in
// index.html injects. Kept as the only file in `src/` that touches
// `window.Telegram` directly, same reasoning as the backend's
// `TelegramGateway` port: everything else in this app should be testable
// (and runnable in a plain browser tab during development) without a
// real Telegram client present.

interface TelegramWebApp {
  initData: string;
  ready: () => void;
  expand: () => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  themeParams?: Record<string, string>;
  colorScheme?: "light" | "dark";
  BackButton: {
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  HapticFeedback?: {
    impactOccurred: (style: "light" | "medium" | "heavy") => void;
  };
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

function webApp(): TelegramWebApp | undefined {
  return window.Telegram?.WebApp;
}

/** Call once at app startup. No-ops outside a real Telegram client (e.g.
 * a plain browser tab during local development), so the rest of the app
 * doesn't need to branch on "am I really inside Telegram?" itself. */
export function initTelegramWebApp(): void {
  const app = webApp();
  if (!app) return;
  app.ready();
  app.expand();
}

/** The signed payload the backend's (not-yet-built) `telegram_init_data`
 * `AuthProvider` adapter will verify - see docs/architecture/auth.md.
 * Empty string outside Telegram, which the backend's bootstrap `null`
 * adapter already handles by simply never authenticating anyone (401 on
 * anything that requires auth), so this file doesn't need its own
 * "running outside Telegram" error handling. */
export function getInitData(): string {
  return webApp()?.initData ?? "";
}

export function hapticTap(): void {
  webApp()?.HapticFeedback?.impactOccurred("light");
}

export function showBackButton(onClick: () => void): () => void {
  const app = webApp();
  if (!app) return () => {};
  app.BackButton.show();
  app.BackButton.onClick(onClick);
  return () => {
    app.BackButton.offClick(onClick);
    app.BackButton.hide();
  };
}
