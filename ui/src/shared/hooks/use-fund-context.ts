"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";

export interface FundInfo {
  fund_slug: string;
  fund_name: string;
  role: string;
}

export function useFundContext() {
  const params = useParams<{ fundSlug: string }>();

  const { data: funds = [], isLoading } = useQuery<FundInfo[]>({
    queryKey: ["me", "funds"],
    queryFn: () => clientFetch<FundInfo[]>("/me/funds"),
    staleTime: 5 * 60 * 1000,
  });

  const activeFund = funds.find((f) => f.fund_slug === params.fundSlug);

  return {
    fundSlug: params.fundSlug,
    fundName: activeFund?.fund_name ?? params.fundSlug,
    role: activeFund?.role ?? null,
    funds,
    isLoading,
  };
}
