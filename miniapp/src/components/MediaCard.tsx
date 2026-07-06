export function MediaCard({
  title,
  subtitle,
  badge,
  onClick,
}: {
  title: string;
  subtitle?: string;
  badge?: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-3 text-left transition active:scale-[0.99] active:bg-neutral-800"
    >
      <div className="flex h-16 w-11 flex-none items-center justify-center rounded bg-neutral-800 text-lg">
        {"\u{1F3AC}"}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{title}</p>
        {subtitle && <p className="truncate text-sm text-neutral-400">{subtitle}</p>}
      </div>
      {badge && (
        <span className="flex-none rounded-full bg-accent/20 px-2 py-0.5 text-xs font-medium text-accent">
          {badge}
        </span>
      )}
    </button>
  );
}
