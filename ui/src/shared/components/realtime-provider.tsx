"use client";

import { useRealtime } from "@/shared/hooks/use-realtime";
import { useFundContext } from "@/shared/hooks/use-fund-context";

/**
 * Mounts the SSE real-time connection for the active fund.
 * Renders nothing visible — just drives cache invalidation.
 */
export function RealtimeProvider() {
  const { fundSlug } = useFundContext();
  useRealtime(fundSlug);
  return null;
}
