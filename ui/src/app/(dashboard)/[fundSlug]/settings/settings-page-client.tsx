"use client";

import { useSession } from "next-auth/react";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { type TableDensity, useTablePreferences } from "@/shared/hooks/use-table-preferences";
import { useTheme } from "@/shared/hooks/use-theme";

const DENSITY_OPTIONS: { label: string; value: TableDensity }[] = [
  { label: "Compact", value: "compact" },
  { label: "Comfortable", value: "comfortable" },
];

const SORT_DIRECTION_OPTIONS: { label: string; value: "asc" | "desc" }[] = [
  { label: "Ascending", value: "asc" },
  { label: "Descending", value: "desc" },
];

const SORT_KEY_OPTIONS = [
  { label: "Created At", value: "created_at" },
  { label: "Updated At", value: "updated_at" },
  { label: "Instrument", value: "instrument_id" },
  { label: "Name", value: "name" },
];

export function SettingsPageClient() {
  const { data: session } = useSession();
  const { fundName, role } = useFundContext();
  const { theme, toggle } = useTheme();
  const { preferences, update } = useTablePreferences();

  const user = session?.user;

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <h1 className="text-2xl font-semibold">Settings</h1>

      {/* User Profile */}
      <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6">
        <h2 className="mb-4 text-lg font-medium">Profile</h2>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-[var(--muted-foreground)]">Name</span>
            <span className="text-sm font-medium">{user?.name ?? "Unknown"}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-[var(--muted-foreground)]">Email</span>
            <span className="text-sm font-medium">{user?.email ?? "Unknown"}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-[var(--muted-foreground)]">Active Fund</span>
            <span className="text-sm font-medium">{fundName}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-[var(--muted-foreground)]">Role</span>
            <span className="text-sm font-medium capitalize">
              {role?.replace(/_/g, " ") ?? "N/A"}
            </span>
          </div>
        </div>
      </section>

      {/* Appearance */}
      <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6">
        <h2 className="mb-4 text-lg font-medium">Appearance</h2>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium">Theme</p>
            <p className="text-xs text-[var(--muted-foreground)]">
              Toggle between dark and light mode
            </p>
          </div>
          <button
            type="button"
            onClick={toggle}
            className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-2 text-sm font-medium transition-colors hover:bg-[var(--accent)]"
          >
            {theme === "dark" ? "Light Mode" : "Dark Mode"}
          </button>
        </div>
      </section>

      {/* Table Display Preferences */}
      <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6">
        <h2 className="mb-4 text-lg font-medium">Table Display</h2>
        <div className="space-y-5">
          {/* Density Toggle */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Row Density</p>
              <p className="text-xs text-[var(--muted-foreground)]">
                Adjust the spacing between table rows
              </p>
            </div>
            <div className="flex items-center gap-1 rounded-lg border border-[var(--border)] p-0.5">
              {DENSITY_OPTIONS.map((opt) => (
                <button
                  type="button"
                  key={opt.value}
                  onClick={() => update({ density: opt.value })}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                    preferences.density === opt.value
                      ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Default Sort Key */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Default Sort Column</p>
              <p className="text-xs text-[var(--muted-foreground)]">
                Initial sort column when opening tables
              </p>
            </div>
            <select
              value={preferences.defaultSortKey}
              onChange={(e) => update({ defaultSortKey: e.target.value })}
              className="rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
            >
              {SORT_KEY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Default Sort Direction */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Default Sort Direction</p>
              <p className="text-xs text-[var(--muted-foreground)]">
                Initial sort order when opening tables
              </p>
            </div>
            <select
              value={preferences.defaultSortDirection}
              onChange={(e) => update({ defaultSortDirection: e.target.value as "asc" | "desc" })}
              className="rounded-md border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
            >
              {SORT_DIRECTION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>
    </div>
  );
}
