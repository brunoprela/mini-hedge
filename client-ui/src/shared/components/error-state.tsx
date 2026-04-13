import { AlertTriangle } from "lucide-react";

export function ErrorState({
  message = "Something went wrong",
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <AlertTriangle size={40} className="text-[var(--destructive)] mb-3" />
      <p className="text-sm font-medium text-[var(--foreground)]">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md border border-[var(--border)] px-4 py-1.5 text-sm hover:bg-[var(--muted)]"
        >
          Try again
        </button>
      )}
    </div>
  );
}
