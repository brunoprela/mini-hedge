"use client";

import { useQuery } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import { ErrorState, LoadingSkeleton } from "@mini-hedge/ui";
import { useFunds } from "@/shared/components/fund-selector";

export default function ProfilePage() {
  const { data: fundsPage, isLoading: fundsLoading, error: fundsError, refetch } = useFunds();
  const funds = fundsPage?.items ?? [];
  const firstSlug = funds[0]?.slug;

  const {
    data: investors,
    isLoading: investorsLoading,
    error: investorsError,
  } = useQuery({
    queryKey: ["profile-investors", firstSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/capital/investors", {
        headers: fundHeaders(firstSlug!),
      });
      if (error) throw error;
      return data;
    },
    enabled: !!firstSlug,
  });

  const isLoading = fundsLoading || investorsLoading;
  const error = fundsError || investorsError;
  const profile = investors?.[0];

  if (error) {
    return <ErrorState message={String(error)} onRetry={() => refetch()} />;
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold text-[var(--foreground-bright)]">Profile</h1>
          <p className="text-sm text-[var(--muted-foreground)]">Your investor account details.</p>
        </div>
        <div className="max-w-lg rounded-lg border border-[var(--border)] bg-[var(--card)] p-8">
          <LoadingSkeleton variant="text" rows={5} />
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold text-[var(--foreground-bright)]">Profile</h1>
          <p className="text-sm text-[var(--muted-foreground)]">Your investor account details.</p>
        </div>
        <div className="max-w-lg rounded-lg border border-[var(--border)] bg-[var(--card)] p-8 text-center text-[var(--muted-foreground)]">
          No investor profile found.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--foreground-bright)]">Profile</h1>
        <p className="text-sm text-[var(--muted-foreground)]">Your investor account details.</p>
      </div>

      <div className="max-w-lg rounded-lg border border-[var(--border)] bg-[var(--card)] divide-y divide-[var(--border)]">
        <div className="px-5 py-4">
          <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
            Entity Name
          </p>
          <p className="mt-1 text-sm font-medium text-[var(--foreground)]">{profile.name}</p>
        </div>
        <div className="px-5 py-4">
          <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
            Email
          </p>
          <p className="mt-1 text-sm text-[var(--foreground)]">
            {profile.contact_email ?? "--"}
          </p>
        </div>
        <div className="px-5 py-4">
          <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
            Entity Type
          </p>
          <p className="mt-1 text-sm text-[var(--foreground)]">
            {profile.entity_type.replace(/_/g, " ")}
          </p>
        </div>
        <div className="px-5 py-4">
          <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
            Tax Jurisdiction
          </p>
          <p className="mt-1 text-sm text-[var(--foreground)]">
            {profile.tax_jurisdiction ?? "--"}
          </p>
        </div>
        <div className="px-5 py-4">
          <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
            Status
          </p>
          <p className="mt-1">
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                profile.is_active
                  ? "bg-[var(--success-muted)] text-[var(--success)]"
                  : "bg-[var(--destructive)]/10 text-[var(--destructive)]"
              }`}
            >
              {profile.is_active ? "Active" : "Inactive"}
            </span>
          </p>
        </div>
      </div>
    </div>
  );
}
