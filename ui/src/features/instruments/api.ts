import { queryOptions } from "@tanstack/react-query";
import { clientFetch } from "@/shared/lib/api";

export interface Instrument {
  id: string;
  ticker: string;
  name: string;
  asset_class: string;
  currency: string;
  exchange: string | null;
  country: string | null;
  sector: string | null;
  is_active: boolean;
}

export function instrumentsQueryOptions(fundSlug: string) {
  return queryOptions({
    queryKey: ["instruments", fundSlug],
    queryFn: () =>
      clientFetch<Instrument[]>("/instruments", { fundSlug }),
  });
}

export function instrumentSearchQueryOptions(fundSlug: string, query: string) {
  return queryOptions({
    queryKey: ["instruments", "search", fundSlug, query],
    queryFn: () =>
      clientFetch<Instrument[]>(`/instruments/search?q=${encodeURIComponent(query)}`, {
        fundSlug,
      }),
    enabled: query.length >= 1,
  });
}
