"use client";

/**
 * Breadcrumbs — automatic breadcrumb trail from a pathname.
 *
 * The consumer supplies:
 *   - `segmentLabels` — map of URL segment to display label (e.g. "portfolio" -> "Portfolios").
 *   - `rootLabel`     — label for the home crumb (e.g. "Dashboard").
 *   - `rootHref`      — URL of the home crumb.
 *   - optional `pathname` override (otherwise `usePathname` is used).
 *   - optional `pathPrefix` that's stripped before splitting (useful for tenanted routes like `/:fundSlug/*`).
 *
 * UUID-like or numeric segments are skipped by default — override via `skipSegment` if needed.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Fragment } from "react";

interface BreadcrumbsProps {
  /** Map of URL segment to friendly label. Unknown segments fall through verbatim. */
  segmentLabels?: Record<string, string>;
  rootLabel?: string;
  rootHref?: string;
  /** Override the pathname (e.g. for testing). Otherwise `usePathname()` is used. */
  pathname?: string;
  /** Prefix to strip before splitting — supports tenant-scoped routes. */
  pathPrefix?: string;
  /** Predicate for segments to skip (IDs, UUIDs). Defaults to UUID-ish or numeric. */
  skipSegment?: (segment: string) => boolean;
  className?: string;
}

const DEFAULT_SKIP = (segment: string): boolean =>
  /^[0-9a-f]{8}-/.test(segment) || /^\d+$/.test(segment);

export function Breadcrumbs({
  segmentLabels = {},
  rootLabel = "Home",
  rootHref = "/",
  pathname: pathnameProp,
  pathPrefix,
  skipSegment = DEFAULT_SKIP,
  className = "",
}: BreadcrumbsProps) {
  const currentPath = usePathname();
  const pathname = pathnameProp ?? currentPath ?? "/";

  const relativePath =
    pathPrefix && pathname.startsWith(pathPrefix) ? pathname.slice(pathPrefix.length) : pathname;

  const parts = relativePath.split("/").filter(Boolean);
  if (parts.length === 0) return null;

  const segments = parts
    .filter((part) => !skipSegment(part))
    .map((part, i, arr) => ({
      label: segmentLabels[part] ?? part,
      path: `${pathPrefix ?? ""}/${arr.slice(0, i + 1).join("/")}`,
    }));

  if (segments.length === 0) return null;

  return (
    <nav
      aria-label="Breadcrumb"
      className={`flex items-center gap-1.5 text-sm text-[var(--muted-foreground)] ${className}`}
    >
      <Link href={rootHref} className="hover:text-[var(--foreground)]">
        {rootLabel}
      </Link>
      {segments.map((seg, i) => (
        <Fragment key={seg.path}>
          <span>/</span>
          {i === segments.length - 1 ? (
            <span className="font-medium text-[var(--foreground)]">{seg.label}</span>
          ) : (
            <Link href={seg.path} className="hover:text-[var(--foreground)]">
              {seg.label}
            </Link>
          )}
        </Fragment>
      ))}
    </nav>
  );
}
