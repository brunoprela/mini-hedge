/**
 * Test utilities for ops-ui.
 *
 * See desk-ui test utils for rationale.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

export function withQueryClient(children: ReactNode, client?: QueryClient) {
  const qc = client ?? makeQueryClient();
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

export function renderWithProviders(ui: ReactElement, options?: RenderOptions) {
  const client = makeQueryClient();
  return {
    client,
    ...render(ui, {
      wrapper: ({ children }) => withQueryClient(children, client),
      ...options,
    }),
  };
}
