/**
 * Global test setup for desk-ui.
 *
 * - Registers jest-dom matchers so we can `expect(el).toBeInTheDocument()`.
 * - Mocks `next/navigation` with stubs for `useRouter`, `usePathname`,
 *   `useSearchParams`, and `useParams`. Tests can override per-case with
 *   `vi.mocked(useParams).mockReturnValue(...)`.
 * - Mocks the `next-auth` client hook so components that touch session state
 *   don't break in isolation.
 */

import "@testing-library/jest-dom/vitest";
import { createElement } from "react";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});

vi.mock("next/navigation", () => {
  const router = {
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  };
  return {
    useRouter: () => router,
    usePathname: () => "/",
    useSearchParams: () => new URLSearchParams(),
    useParams: () => ({ fundSlug: "test-fund" }),
    redirect: vi.fn(),
    notFound: vi.fn(),
  };
});

vi.mock("next-auth/react", () => ({
  useSession: () => ({ data: null, status: "unauthenticated" }),
  signIn: vi.fn(),
  signOut: vi.fn(),
  SessionProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// Stub next/link with a plain <a> — avoids Next router internals leaking into
// jsdom and keeps navigation semantics observable in tests.
vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...rest
  }: {
    children: React.ReactNode;
    href: string;
  } & React.AnchorHTMLAttributes<HTMLAnchorElement>) =>
    createElement("a", { href, ...rest }, children),
}));
