import { queryOptions } from "@tanstack/react-query";
import { api, fundHeaders } from "@/shared/lib/api-client";
import type { Instrument } from "./types";

export type { Instrument };

export function instrumentsQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["instruments", fundSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/instruments", {
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
  });
}

export function instrumentSearchQueryOptions(fundSlug: string, query: string) {
  return queryOptions({
    queryKey: ["instruments", "search", fundSlug, query],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/instruments/search", {
        params: { query: { q: query } },
        headers: fundHeaders(fundSlug),
      });
      if (error) throw error;
      return data;
    },
    enabled: query.length >= 1,
  });
}
