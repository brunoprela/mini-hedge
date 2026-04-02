"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { positionsQueryOptions } from "../api";

export function usePositions(portfolioId: string) {
  const { fundSlug } = useFundContext();
  return useQuery(positionsQueryOptions(fundSlug, portfolioId));
}
