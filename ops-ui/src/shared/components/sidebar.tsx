"use client";

import {
  BarChart3,
  Building2,
  CheckSquare,
  ClipboardCheck,
  Database,
  Eye,
  GitCompare,
  Globe,
  Handshake,
  History,
  Key,
  Mail,
  Repeat,
  ScrollText,
  Send,
  Shield,
  TrendingUp,
  Users,
  Sun,
  ArrowLeftRight,
  Banknote,
  Calculator,
  Receipt,
  Landmark,
  UserCheck,
  FileBarChart,
  FileText,
  AlertTriangle,
  Archive,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";

interface NavSection {
  title: string;
  items: { href: string; label: string; icon: React.ComponentType<{ size?: number }> }[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    title: "Overview",
    items: [{ href: "/", label: "Dashboard", icon: BarChart3 }],
  },
  {
    title: "Operations",
    items: [
      { href: "/eod", label: "EOD Control", icon: Sun },
      { href: "/reconciliation", label: "Reconciliation", icon: ArrowLeftRight },
      { href: "/cash", label: "Cash & Settlement", icon: Banknote },
      { href: "/fees", label: "Fee Management", icon: Receipt },
      { href: "/fee-approval", label: "Fee Approval", icon: CheckSquare },
      { href: "/corporate-actions", label: "Corporate Actions", icon: Landmark },
      { href: "/nav", label: "NAV Review", icon: TrendingUp },
      { href: "/nav-computation", label: "NAV Computation", icon: Calculator },
      { href: "/price-validation", label: "Price Validation", icon: Eye },
      { href: "/trade-recon", label: "Trade Recon", icon: GitCompare },
      { href: "/settlement-instructions", label: "SSI / SWIFT", icon: Send },
      { href: "/fails-management", label: "Fails Management", icon: XCircle },
    ],
  },
  {
    title: "Capital",
    items: [
      { href: "/subscriptions", label: "Subscriptions", icon: UserCheck },
      { href: "/redemptions", label: "Redemptions", icon: UserCheck },
    ],
  },
  {
    title: "Reporting",
    items: [
      { href: "/regulatory", label: "Regulatory", icon: FileText },
      { href: "/client-reporting", label: "Client Reporting", icon: Mail },
      { href: "/custom-reports", label: "Custom Reports", icon: FileBarChart },
    ],
  },
  {
    title: "Platform",
    items: [
      { href: "/customers", label: "Customers", icon: Handshake },
      { href: "/users", label: "Users", icon: Users },
      { href: "/funds", label: "Funds", icon: Building2 },
      { href: "/operators", label: "Operators", icon: Shield },
      { href: "/audit", label: "Audit Log", icon: ScrollText },
      { href: "/dlq", label: "Dead Letters", icon: AlertTriangle },
      { href: "/archival", label: "Archival", icon: Archive },
      { href: "/data-quality", label: "Data Quality", icon: Database },
      { href: "/change-history", label: "Change History", icon: History },
      { href: "/sign-off", label: "Sign-Off Records", icon: ClipboardCheck },
      { href: "/client-switcher", label: "Client Switcher", icon: Repeat },
      { href: "/cross-client", label: "Cross-Client Dashboard", icon: Globe },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-full w-[var(--sidebar-width)] border-r border-[var(--border)] bg-[var(--card)] flex flex-col">
      <div className="p-4 border-b border-[var(--border)]">
        <h1 className="text-lg font-semibold text-[var(--primary)]">Ops Console</h1>
        <p className="text-xs text-[var(--muted-foreground)]">Platform Administration</p>
      </div>

      <nav className="flex-1 overflow-y-auto p-2">
        {NAV_SECTIONS.map((section) => (
          <div key={section.title} className="mb-3">
            <p className="mb-1 px-3 text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
              {section.title}
            </p>
            <div className="space-y-0.5">
              {section.items.map(({ href, label, icon: Icon }) => {
                const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm ${
                      active
                        ? "bg-[var(--accent)] text-[var(--accent-foreground)] font-medium"
                        : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
                    }`}
                  >
                    <Icon size={15} />
                    {label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="p-2 border-t border-[var(--border)]">
        <button
          type="button"
          onClick={() => signOut({ callbackUrl: "/login" })}
          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
        >
          <Key size={16} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
