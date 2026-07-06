import { useEffect, useReducer } from "react";
import { BottomNav } from "./components/BottomNav";
import { SearchPage } from "./pages/SearchPage";
import { BrowsePage } from "./pages/BrowsePage";
import { MediaDetailsPage } from "./pages/MediaDetailsPage";
import { PlayerPage } from "./pages/PlayerPage";
import { initialNavigationState, navigationReducer } from "./lib/navigation";
import { initTelegramWebApp, showBackButton } from "./lib/telegram";
import type { SearchResultGroup } from "./types";

export default function App() {
  const [nav, dispatch] = useReducer(navigationReducer, initialNavigationState);
  const route = nav.stack[nav.stack.length - 1];
  const canGoBack = nav.stack.length > 1;

  useEffect(() => {
    initTelegramWebApp();
  }, []);

  // Mirrors Telegram's native back button to this app's own navigation
  // stack, so a user swiping/tapping Telegram's chrome back button
  // behaves the same as this app's in-page back arrows.
  useEffect(() => {
    if (!canGoBack) return;
    return showBackButton(() => dispatch({ type: "back" }));
  }, [canGoBack]);

  return (
    <div className="min-h-full">
      {route.name === "search" && (
        <SearchPage
          onOpenGroup={(group: SearchResultGroup) =>
            dispatch({
              type: "push",
              route: { name: "details", title: group.title, year: group.year },
            })
          }
        />
      )}

      {(route.name === "browse" || route.name === "genre") && (
        <BrowsePage
          genre={route.name === "genre" ? route.genre : null}
          onSelectGenre={(genre) => dispatch({ type: "push", route: { name: "genre", genre } })}
          onBack={() => dispatch({ type: "back" })}
          onOpenItem={(item) =>
            dispatch({
              type: "push",
              route: { name: "details", title: item.title, year: item.year },
            })
          }
        />
      )}

      {route.name === "details" && (
        <MediaDetailsPage
          title={route.title}
          year={route.year}
          onBack={() => dispatch({ type: "back" })}
          onSelectVariant={(mediaId, displayTitle) =>
            dispatch({ type: "push", route: { name: "player", mediaId, title: displayTitle } })
          }
        />
      )}

      {route.name === "player" && (
        <PlayerPage
          mediaId={route.mediaId}
          title={route.title}
          onBack={() => dispatch({ type: "back" })}
        />
      )}

      <BottomNav
        current={route}
        onNavigate={(target) => dispatch({ type: "reset", route: target })}
      />
    </div>
  );
}
