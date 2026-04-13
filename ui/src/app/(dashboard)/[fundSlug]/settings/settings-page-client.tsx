"use client";

import { useSession } from "next-auth/react";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { useNotificationPreferences } from "@/shared/hooks/use-notification-preferences";
import { type TableDensity, useTablePreferences } from "@/shared/hooks/use-table-preferences";
import { useTheme } from "@/shared/hooks/use-theme";
import { ApiKeyManagement } from "@/features/settings/components/api-key-management";
import { ActivityLog } from "@/features/settings/components/activity-log";

/* ------------------------------------------------------------------ */
/*  Toggle switch                                                     */
/* ------------------------------------------------------------------ */

function Toggle({
  checked,
  onChange,
  disabled = false,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)] ${
        disabled
          ? "cursor-not-allowed opacity-40"
          : "cursor-pointer"
      } ${checked ? "bg-[var(--primary)]" : "bg-[var(--border)]"}`}
    >
      <span
        className={`pointer-events-none block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform ${
          checked ? "translate-x-4" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  Notification category / delivery row                              */
/* ------------------------------------------------------------------ */

function NotificationRow({
  label,
  description,
  checked,
  onChange,
  disabled = false,
  badge,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  badge?: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm font-medium">
          {label}
          {badge && (
            <span className="ml-2 rounded-full border border-[var(--border)] px-2 py-0.5 text-[10px] text-[var(--muted-foreground)]">
              {badge}
            </span>
          )}
        </p>
        <p className="text-xs text-[var(--muted-foreground)]">{description}</p>
      </div>
      <Toggle checked={checked} onChange={onChange} disabled={disabled} />
    </div>
  );
}

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
  const { preferences: notifPrefs, update: updateNotif } = useNotificationPreferences();

  const user = session?.user;

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <h1 className="text-sm font-semibold">Settings</h1>

      {/* User Profile */}
      <section className="rounded-md border border-[var(--border)] bg-[var(--card)] p-6">
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Profile
        </h2>
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
      <section className="rounded-md border border-[var(--border)] bg-[var(--card)] p-6">
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Appearance
        </h2>
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
            className="rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-sm font-medium transition-colors hover:bg-[var(--accent)]"
          >
            {theme === "dark" ? "Light Mode" : "Dark Mode"}
          </button>
        </div>
      </section>

      {/* Table Display Preferences */}
      <section className="rounded-md border border-[var(--border)] bg-[var(--card)] p-6">
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Table Display
        </h2>
        <div className="space-y-5">
          {/* Density Toggle */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Row Density</p>
              <p className="text-xs text-[var(--muted-foreground)]">
                Adjust the spacing between table rows
              </p>
            </div>
            <div className="flex items-center gap-1 rounded-md border border-[var(--border)] p-0.5">
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

      {/* Notification Categories */}
      <section className="rounded-md border border-[var(--border)] bg-[var(--card)] p-6">
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Notifications
        </h2>
        <div className="space-y-5">
          <NotificationRow
            label="Order notifications"
            description="Fills, cancellations, and rejections"
            checked={notifPrefs.orders}
            onChange={(v) => updateNotif({ orders: v })}
          />
          <NotificationRow
            label="Compliance alerts"
            description="Violations and breaches"
            checked={notifPrefs.compliance}
            onChange={(v) => updateNotif({ compliance: v })}
          />
          <NotificationRow
            label="EOD notifications"
            description="Run started, completed, or failed"
            checked={notifPrefs.eod}
            onChange={(v) => updateNotif({ eod: v })}
          />
          <NotificationRow
            label="Market data alerts"
            description="Price threshold triggers"
            checked={notifPrefs.marketData}
            onChange={(v) => updateNotif({ marketData: v })}
          />
          <NotificationRow
            label="System notifications"
            description="Connection status and errors"
            checked={notifPrefs.system}
            onChange={(v) => updateNotif({ system: v })}
          />
        </div>
      </section>

      {/* Notification Delivery */}
      <section className="rounded-md border border-[var(--border)] bg-[var(--card)] p-6">
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          Notification Delivery
        </h2>
        <div className="space-y-5">
          <NotificationRow
            label="In-app toasts"
            description="Show notifications as toast popups in the app"
            checked={notifPrefs.inAppToasts}
            onChange={(v) => updateNotif({ inAppToasts: v })}
          />
          <NotificationRow
            label="Email"
            description="Receive notification summaries via email"
            checked={notifPrefs.email}
            onChange={(v) => updateNotif({ email: v })}
            disabled
            badge="Coming soon"
          />
          <NotificationRow
            label="Browser push"
            description="Receive push notifications in your browser"
            checked={notifPrefs.browserPush}
            onChange={(v) => updateNotif({ browserPush: v })}
            disabled
            badge="Coming soon"
          />
        </div>
      </section>

      {/* API Keys */}
      <ApiKeyManagement />

      {/* Activity / Audit Log */}
      <ActivityLog />
    </div>
  );
}
