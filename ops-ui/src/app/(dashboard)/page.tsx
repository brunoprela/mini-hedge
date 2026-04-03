"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2, Shield, Users } from "lucide-react";
import { apiFetch } from "@/shared/lib/api";

interface UserInfo {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
}

interface FundDetail {
  id: string;
  slug: string;
  name: string;
  status: string;
}

interface OperatorInfo {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  platform_role: string | null;
}

export default function DashboardPage() {
  const users = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => apiFetch<UserInfo[]>("admin/users"),
  });
  const funds = useQuery({
    queryKey: ["admin", "funds"],
    queryFn: () => apiFetch<FundDetail[]>("admin/funds"),
  });
  const operators = useQuery({
    queryKey: ["admin", "operators"],
    queryFn: () => apiFetch<OperatorInfo[]>("admin/operators"),
  });

  const cards = [
    { label: "Users", count: users.data?.length ?? "-", icon: Users, color: "text-blue-600" },
    { label: "Funds", count: funds.data?.length ?? "-", icon: Building2, color: "text-green-600" },
    {
      label: "Operators",
      count: operators.data?.length ?? "-",
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
