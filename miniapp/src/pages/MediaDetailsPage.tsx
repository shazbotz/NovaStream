import { useEffect, useState } from "react";
import { search } from "../lib/api-client";
import type { SearchResultGroup, SearchVariant } from "../types";
import { Header } from "../components/Header";
import { EmptyState, ErrorBanner, LoadingSpinner } from "../components/Feedback";

/** Groups a title's variants by language, matching the reference
 * screenshot's "Select Variant / English / Hindi" sections - purely a
 * presentation grouping on top of the already-grouped `SearchResultGroup`
 * (see `plugins/features/catalog_search/grouping.py`), no extra API call. */
function byLanguage(variants: SearchVariant[]): Map<string, SearchVariant[]> {
  const map = new Map<string, SearchVariant[]>();
  for (const variant of variants) {
    const list = map.get(variant.language) ?? [];
    list.push(variant);
    map.set(variant.language, list);
  }
  return map;
}

function formatSize(bytes: number): string {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)}GB`;
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(0)}MB`;
  return `${bytes}B`;
}

export function MediaDetailsPage({
  title,
  year,
  preloadedGroup,
  onBack,
  onSelectVariant,
}: {
  title: string;
  year: number | null;
  preloadedGroup?: SearchResultGroup;
  onBack: () => void;
  onSelectVariant: (mediaId: string, displayTitle: string) => void;
}) {
  const [group, setGroup] = useState<SearchResultGroup | null>(preloadedGroup ?? null);
  const [loading, setLoading] = useState(!preloadedGroup);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (preloadedGroup) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    search(title)
      .then((res) => {
        if (cancelled) return;
        const match =
          res.results.find((g) => g.title === title && g.year === year) ?? res.results[0] ?? null;
        setGroup(match);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, year]);

  return (
    <div className="pb-20">
      <Header title={title} onBack={onBack} />

      {loading && <LoadingSpinner />}
      {error && <ErrorBanner message={error} />}
      {!loading && !error && !group && <EmptyState message="No variants found for this title" />}

      {group && (
        <div className="px-4 pt-4">
          <div className="mb-4 flex h-40 w-full items-center justify-center rounded-lg bg-neutral-900 text-4xl">
            {"\u{1F3AC}"}
          </div>
          <h2 className="text-xl font-semibold">{group.title}</h2>
          <p className="mt-1 text-sm text-neutral-400">
            {[group.year, `${group.variant_count} variant${group.variant_count === 1 ? "" : "s"}`]
              .filter(Boolean)
              .join(" \u00b7 ")}
          </p>

          <div className="mt-5 flex flex-col gap-5">
            {Array.from(byLanguage(group.variants)).map(([language, variants]) => (
              <div key={language}>
                <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-400">
                  {language}
                </h3>
                <div className="flex flex-col gap-2">
                  {variants.map((variant) => (
                    <button
                      key={variant.media_id}
                      onClick={() => onSelectVariant(variant.media_id, group.title)}
                      className="flex items-center justify-between rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2.5 text-left text-sm transition active:bg-neutral-800"
                    >
                      <span>
                        {variant.quality} {"\u00b7"} {variant.release_type} {"\u00b7"} {variant.codec}
                      </span>
                      <span className="flex items-center gap-2 text-neutral-400">
                        {formatSize(variant.file_size)}
                        <span className="text-accent">{"\u25B6"}</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
