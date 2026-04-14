"use client";
import { signIn } from "next-auth/react";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--muted)]">
      <div className="w-full max-w-sm rounded-lg border border-[var(--border)] bg-[var(--card)] p-8 shadow-sm">
        <h1 className="mb-1 text-xl font-semibold text-[var(--foreground)]">Investor Portal</h1>
        <p className="mb-6 text-sm text-[var(--muted-foreground)]">
          Sign in to access your investments
        </p>
        <button
          type="button"
          onClick={() => signIn("keycloak", { callbackUrl: "/" })}
          className="w-full rounded-md bg-[var(--primary)] px-4 py-2.5 text-sm font-medium text-white hover:opacity-90"
        >
          Sign in
        </button>
      </div>
    </div>
  );
}
