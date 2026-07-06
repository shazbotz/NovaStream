import { useEffect, useState } from "react";
import { BROWSE_GENRES, browseGenre } from "../lib/api-client";
import type { GenreListItem } from "../types";
import { MediaCard } from "../components/MediaCard";
import { EmptyState, ErrorBanner, LoadingSpinner } from "../components/Feedback";
import { Header } from "../components/Header";

function GenreGrid({ onSelect }: { onSelect: (genre: string) => void }) {
  return (
    <div className="grid grid-cols-2 gap-3 p-4">
      {BROWSE_GENRES.map((genre) => (
        <button
          key={genre}
          onClick={() => onSelect(genre)}
          className="rounded-lg border border-neutral-800 bg-neutral-900 py-4 text-center text-sm font-medium transition active:scale-[0.98] active:bg-neutral-800"
        >
          {genre}
        </button>
      ))}
    </div>
  );
}

function GenreItemList({
  genre,
  onOpenItem,
}: {
  genre: string;
  onOpenItem: (item: GenreListItem) => void;
}) {
  const [items, setItems] = useState<GenreListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    browseGenre(genre)
      .then((res) => {
        if (!cancelled) setItems(res.items);
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
  }, [genre]);

  if (loading) return <LoadingSpinner label={`Loading ${genre}...`} />;
  if (error) return <ErrorBanner message={error} />;
  if (items.length === 0) return <EmptyState message={`Nothing tagged "${genre}" yet`} />;

  return (
    <div className="flex flex-col gap-2 px-4 pt-3">
      {items.map((item) => (
        <MediaCard
          key={item.media_id}
          title={item.title}
          subtitle={item.year ? String(item.year) : undefined}
          onClick={() => onOpenItem(item)}
        />
      ))}
    </div>
  );
}

export function BrowsePage({
  genre,
  onSelectGenre,
  onBack,
  onOpenItem,
}: {
  genre: string | null;
  onSelectGenre: (genre: string) => void;
  onBack: () => void;
  onOpenItem: (item: GenreListItem) => void;
}) {
  return (
    <div className="pb-20">
      <Header title={genre ?? "Browse Genres"} onBack={genre ? onBack : undefined} />
      {genre ? (
        <GenreItemList genre={genre} onOpenItem={onOpenItem} />
      ) : (
        <GenreGrid onSelect={onSelectGenre} />
      )}
    </div>
  );
}
