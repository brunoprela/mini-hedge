"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { latestPriceQueryOptions } from "../api";

export function useLatestPrice(instrumentId: string) {
  const { fundSlug } = useFundContext();
  return useQuery(latestPriceQueryOptions(fundSlug, instrumentId));
}
