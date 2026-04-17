"use client";

/**
 * Sidebar — nav shell used by all three UIs.
 *
 * Each UI has its own navigation config (ops has many admin sections; client has a flat
 * investor-portal nav; desk has collapsible module groups scoped by fund). Instead of
 * shipping one rigid tree, this primitive renders a *shell* that the consumer
 * fills via props:
 *
 *   - `header`   — logo / portal title (a consumer-specific node)
 *   - `sections` — NavSection[]; each section has an optional title and items
 *   - `footer`   — user block / logout button
 *
 * Items accept a custom `isActive` predicate so consumers can handle fund-slug
 * prefixes or custom route matching without the primitive knowing about them.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  useState,
  type ComponentType,
  type ReactNode,
} from "react";

export interface SidebarItem {
  /** Destination URL. */
  href: string;
  /** Display label. */
  label: ReactNode;
  /** Optional leading icon component — rendered with `size`. */
  icon?: ComponentType<{ size?: number; className?: string }>;
  /**
   * Custom active-state predicate. Receives the current pathname.
   * Defaults to: `href === "/" ? pathname === "/" : pathname.startsWith(href)`.
   */
  isActive?: (pathname: string) => boolean;
}

export interface SidebarSection {
  /** Optional section heading. If omitted the section renders as an ungrouped cluster. */
  title?: string;
  items: SidebarItem[];
  /** For collapsible sections — defaults to open. */
  defaultOpen?: boolean;
  /** When true, the section renders as a static group without a toggle. Defaults to true. */
  collapsible?: boolean;
}

interface SidebarProps {
  sections: SidebarSection[];
  /** Rendered above the nav list. Typically the brand/logo block. */
  header?: ReactNode;
  /** Rendered below the nav list. Typically the user block and logout. */
  footer?: ReactNode;
  /** Override the aside class list — rarely needed. */
  className?: string;
}

export function Sidebar({ sections, header, footer, className = "" }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className={`flex h-full w-[var(--sidebar-width)] flex-col border-r border-[var(--border)] bg-[var(--sidebar,var(--card))] ${className}`}
    >
      {header && (
        <div className="border-b border-[var(--border)] px-4 py-4">{header}</div>
      )}

      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {sections.map((section, i) => (
          <SidebarSectionImpl
            // biome-ignore lint/suspicious/noArrayIndexKey: sections array is stable per render
            key={section.title ?? `section-${i}`}
            section={section}
            pathname={pathname}
          />
        ))}
      </nav>

      {footer && <div className="border-t border-[var(--border)] p-2">{footer}</div>}
    </aside>
  );
}

function SidebarSectionImpl({
  section,
  pathname,
}: {
  section: SidebarSection;
  pathname: string;
}) {
  const collapsible = section.collapsible ?? false;
  const [open, setOpen] = useState(section.defaultOpen ?? true);

  const listContent = (
    <div className="space-y-0.5">
      {section.items.map((item) => (
        <SidebarLink key={item.href} item={item} pathname={pathname} />
      ))}
    </div>
  );

  if (!section.title) {
    return <div className="mb-3">{listContent}</div>;
  }

  if (!collapsible) {
    return (
      <div className="mb-3">
        <p className="mb-1 px-3 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          {section.title}
        </p>
        {listContent}
      </div>
    );
  }

  return (
    <div className="mb-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
        aria-expanded={open}
      >
        {section.title}
        <span
          aria-hidden="true"
          className={`inline-block h-2 w-2 border-r border-b border-current transition-transform ${
            open ? "rotate-45" : "-rotate-45"
          }`}
        />
      </button>
      {open && listContent}
    </div>
  );
}

function SidebarLink({ item, pathname }: { item: SidebarItem; pathname: string }) {
  const active = item.isActive
    ? item.isActive(pathname)
    : item.href === "/"
      ? pathname === "/"
      : pathname.startsWith(item.href);

  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors ${
        active
          ? "bg-[var(--sidebar-active,var(--accent))] text-[var(--primary)] font-medium"
          : "text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
      }`}
    >
      {Icon && <Icon size={15} />}
      {item.label}
    </Link>
  );
}
