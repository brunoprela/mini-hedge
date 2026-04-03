"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2, Shield, Users } from "lucide-react";
import { ErrorState } from "@/shared/components/error-state";
import { CardSkeleton } from "@/shared/components/loading-skeleton";
import { apiFetch } from "@/shared/lib/api";
import type { FundDetail, OperatorInfo, Page, UserInfo } from "@/shared/types";

export default function DashboardPage() {
  const users = useQuery({
    queryKey: ["admin", "users", { limit: 1 }],
    queryFn: () => apiFetch<Page<UserInfo>>("admin/users?limit=1"),
  });
  const funds = useQuery({
    queryKey: ["admin", "funds", { limit: 1 }],
    queryFn: () => apiFetch<Page<FundDetail>>("admin/funds?limit=1"),
  });
  const operators = useQuery({
    queryKey: ["admin", "operators", { limit: 1 }],
    queryFn: () => apiFetch<Page<OperatorInfo>>("admin/operators?limit=1"),
  });

  const isLoading = users.isLoading || funds.isLoading || operators.isLoading;
  const isError = users.isError || funds.isError || operators.isError;

  if (isLoading) {
    return (
      <div>
        <h2 className="text-xl font-semibold mb-6">Dashboard</h2>
        <CardSkeleton count={3} />
      </div>
    );
  }

  if (isError) {
    return (
      <div>
        <h2 className="text-xl font-semibold mb-6">Dashboard</h2>
        <ErrorState
          message="Failed to load dashboard data"
          onRetry={() => {
            users.refetch();
            funds.refetch();
            operators.refetch();
          }}
        />
      </div>
    );
  }

  const cards = [
    { label: "Users", count: users.data?.total ?? 0, icon: Users, color: "text-blue-600" },
    { label: "Funds", count: funds.data?.total ?? 0, icon: Building2, color: "text-green-600" },
    {
      label: "Operators",
      count: operators.data?.total ?? 0,
      icon: Shield,
      color: "text-purple-600",
    },
  ];

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Dashboard</h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {cards.map(({ label, count, icon: Icon, color }) => (
          <div key={label} className="rounded-lg border border-[var(--border)] p-6 bg-white">
            <div className="flex items-center gap-3 mb-2">
              <Icon size={20} className={color} />
              <span className="text-sm text-[var(--muted-foreground)]">{label}</span>
            </div>
            <p className="text-3xl font-bold">{count}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
