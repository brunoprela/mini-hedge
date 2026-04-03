"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { instrumentSearchQueryOptions, instrumentsQueryOptions } from "../api";

export function useInstruments() {
  const { fundSlug } = useFundContext();
  return useQuery(instrumentsQueryOptions(fundSlug));
}

export function useInstrumentSearch(query: string) {
  const { fundSlug } = useFundContext();
  return useQuery(instrumentSearchQueryOptions(fundSlug, query));
}
