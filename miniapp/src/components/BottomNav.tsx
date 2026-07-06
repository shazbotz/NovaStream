import type { Route } from "../lib/navigation";
import { hapticTap } from "../lib/telegram";

interface Tab {
  label: string;
  icon: string;
  route: Route;
  matches: (r: Route) => boolean;
}

const TABS: Tab[] = [
  {
    label: "Search",
    icon: "\u{1F50D}",
    route: { name: "search" },
    matches: (r) => r.name === "search",
  },
  {
    label: "Browse",
    icon: "\u{1F4DA}",
    route: { name: "browse" },
    matches: (r) => r.name === "browse" || r.name === "genre",
  },
];

export function BottomNav({
  current,
  onNavigate,
}: {
  current: Route;
  onNavigate: (route: Route) => void;
}) {
  return (
    <nav className="fixed inset-x-0 bottom-0 flex border-t border-neutral-800 bg-neutral-950/95 backdrop-blur">
      {TABS.map((tab) => {
        const active = tab.matches(current);
        return (
          <button
            key={tab.label}
            onClick={() => {
              hapticTap();
              onNavigate(tab.route);
            }}
            className={`flex flex-1 flex-col items-center gap-0.5 py-2.5 text-xs ${
              active ? "text-accent" : "text-neutral-500"
            }`}
          >
            <span className="text-lg leading-none">{tab.icon}</span>
            {tab.label}
          </button>
        );
      })}
    </nav>
  );
}
