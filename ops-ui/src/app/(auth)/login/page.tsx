import { signIn } from "@/shared/lib/auth";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-sm space-y-6 rounded-lg border border-[var(--border)] p-8">
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-semibold text-[var(--primary)]">Ops Console</h1>
          <p className="text-sm text-[var(--muted-foreground)]">Sign in to manage the platform</p>
        </div>
        <form
          action={async () => {
            "use server";
            await signIn("keycloak", { redirectTo: "/" });
          }}
        >
          <button
            type="submit"
            className="w-full rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
          >
            Sign in with SSO
          </button>
        </form>
      </div>
    </div>
  );
}
