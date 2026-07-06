export function LoadingSpinner({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-neutral-400">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-neutral-700 border-t-accent" />
      <p className="text-sm">{label}</p>
    </div>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="mx-4 mt-4 rounded-lg border border-red-900 bg-red-950/50 px-4 py-3 text-sm text-red-200">
      <p>{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 font-medium text-red-100 underline">
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return <p className="px-4 py-12 text-center text-sm text-neutral-500">{message}</p>;
}
