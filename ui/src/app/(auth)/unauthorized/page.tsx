import Link from "next/link";

export default function UnauthorizedPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="space-y-3 text-center">
        <h1 className="text-2xl font-semibold">Access Denied</h1>
        <p className="text-[var(--muted-foreground)]">
          You do not have permission to access this page.
        </p>
        <Link
          href="/"
          className="inline-block rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
        >
          Go to Dashboard
        </Link>
      </div>
    </div>
  );
}
