import { useEffect, useMemo, useState } from "react";
import { search } from "../lib/api-client";
import type { SearchResponse, SearchResultGroup } from "../types";
import { MediaCard } from "../components/MediaCard";
import { EmptyState, ErrorBanner, LoadingSpinner } from "../components/Feedback";

export function SearchPage({
  onOpenGroup,
}: {
  onOpenGroup: (group: SearchResultGroup) => void;
}) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debounced so typing "Interstellar" doesn't fire 13 requests - the
  // Mini App is the one client of `GET /api/search` likely to be typed
  // into live, unlike `POST /api/media` or bot commands.
  useEffect(() => {
    const handle = setTimeout(() => setDebounced(query.trim()), 300);
    return () => clearTimeout(handle);
  }, [query]);

  useEffect(() => {
    if (!debounced) {
      setResponse(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    search(debounced)
      .then((res) => {
        if (!cancelled) setResponse(res);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [debounced]);

  const results = useMemo(() => response?.results ?? [], [response]);

  return (
    <div className="pb-20">
      <div className="sticky top-0 z-10 border-b border-neutral-800 bg-neutral-950/95 px-4 py-3 backdrop-blur">
        <input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search movies, series, anime..."
          className="w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm outline-none placeholder:text-neutral-500 focus:border-accent"
        />
      </div>

      {loading && <LoadingSpinner label="Searching..." />}
      {error && <ErrorBanner message={error} onRetry={() => setDebounced((d) => d)} />}
      {!loading && !error && debounced && results.length === 0 && (
        <EmptyState message={`No results for "${debounced}"`} />
      )}
      {!debounced && !loading && <EmptyState message="Start typing to search the catalog" />}

      <div className="flex flex-col gap-2 px-4 pt-3">
        {results.map((group) => (
          <MediaCard
            key={`${group.title}-${group.year ?? "na"}`}
            title={group.title}
            subtitle={[group.year, `${group.variant_count} variant${group.variant_count === 1 ? "" : "s"}`]
              .filter(Boolean)
              .join(" \u00b7 ")}
            badge={group.qualities[0]}
            onClick={() => onOpenGroup(group)}
          />
        ))}
      </div>
    </div>
  );
}
