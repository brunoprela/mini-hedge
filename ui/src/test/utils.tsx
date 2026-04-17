/**
 * Test utilities for desk-ui.
 *
 * `renderWithProviders` wraps a component tree in a fresh QueryClient so React
 * Query hooks (`useQuery`, `useMutation`) behave predictably in tests:
 * retries are disabled so rejected queries surface immediately, and each call
 * gets its own cache so no state leaks between tests.
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
