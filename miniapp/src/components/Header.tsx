export function Header({
  title,
  onBack,
}: {
  title: string;
  onBack?: () => void;
}) {
  return (
    <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-neutral-800 bg-neutral-950/95 px-4 py-3 backdrop-blur">
      {onBack && (
        <button
          onClick={onBack}
          aria-label="Back"
          className="text-xl leading-none text-neutral-300"
        >
          {"\u2039"}
        </button>
      )}
      <h1 className="truncate text-base font-semibold">{title}</h1>
    </header>
  );
}
