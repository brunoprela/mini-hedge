"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import type { FundInfo } from "@/features/platform/types";
import { api } from "@/shared/lib/api-client";

export function useFundContext() {
  const params = useParams<{ fundSlug: string }>();

  const { data: funds = [], isLoading } = useQuery<FundInfo[]>({
    queryKey: ["me", "funds"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/me/funds", {});
      if (error) throw error;
      return (data ?? []) as unknown as FundInfo[];
    },
    staleTime: 5 * 60 * 1000,
  });

  const activeFund = funds.find((f) => f.fund_slug === params.fundSlug);

  return {
    fundSlug: params.fundSlug,
    fundName: activeFund?.fund_name ?? params.fundSlug,
    role: activeFund?.role ?? null,
    customerId: activeFund?.customer_id ?? null,
    customerName: activeFund?.customer_name ?? null,
    funds,
    isLoading,
  };
}
