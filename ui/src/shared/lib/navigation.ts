import { Permission } from "./permissions";

export interface NavItem {
  label: string;
  href: string;
  icon:
    | "LayoutDashboard"
    | "Briefcase"
    | "Search"
    | "TrendingUp"
    | "ShieldCheck"
    | "ClipboardList"
    | "BarChart3"
    | "AlertTriangle"
    | "Wallet"
    | "PieChart"
    | "Lightbulb"
    | "Users"
    | "Settings"
    | "ArrowLeftRight"
    | "Calendar"
    | "Receipt"
    | "Activity"
    | "FileText"
    | "ClipboardCheck";
  permission?: Permission;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "", icon: "LayoutDashboard" },

  // Trading
  {
    label: "Portfolios",
    href: "/portfolio",
    icon: "Briefcase",
    permission: Permission.POSITIONS_READ,
  },
  {
    label: "Orders",
    href: "/orders",
    icon: "ClipboardList",
    permission: Permission.ORDERS_READ,
  },
  {
    label: "TCA",
    href: "/tca",
    icon: "Activity",
    permission: Permission.ORDERS_READ,
  },
  {
    label: "Exposure",
    href: "/exposure",
    icon: "BarChart3",
    permission: Permission.EXPOSURE_READ,
  },
  {
    label: "FX Hedging",
    href: "/fx-hedging",
    icon: "ArrowLeftRight",
    permission: Permission.FX_HEDGING_READ,
  },

  // Analytics
  {
    label: "Attribution",
    href: "/attribution",
    icon: "PieChart",
    permission: Permission.ATTRIBUTION_READ,
  },
  {
    label: "Risk",
    href: "/risk",
    icon: "AlertTriangle",
    permission: Permission.RISK_READ,
  },
  {
    label: "Alpha",
    href: "/alpha",
    icon: "Lightbulb",
    permission: Permission.ALPHA_READ,
  },

  // Operations
  {
    label: "Investors",
    href: "/investors",
    icon: "Users",
    permission: Permission.CAPITAL_READ,
  },
  {
    label: "Operations",
    href: "/operations",
    icon: "ClipboardCheck",
    permission: Permission.CAPITAL_READ,
  },
  {
    label: "Cash",
    href: "/cash",
    icon: "Wallet",
    permission: Permission.CASH_READ,
  },
  {
    label: "EOD & NAV",
    href: "/eod",
    icon: "Calendar",
    permission: Permission.RISK_READ,
  },
  {
    label: "Fees",
    href: "/fees",
    icon: "Receipt",
    permission: Permission.CAPITAL_READ,
  },

  // Compliance
  {
    label: "Compliance",
    href: "/compliance",
    icon: "ShieldCheck",
    permission: Permission.COMPLIANCE_READ,
  },

  // Corporate Actions
  {
    label: "Corp Actions",
    href: "/corporate-actions",
    icon: "FileText",
    permission: Permission.POSITIONS_READ,
  },

  // Market Data
  {
    label: "Instruments",
    href: "/instruments",
    icon: "Search",
    permission: Permission.INSTRUMENTS_READ,
  },
  {
    label: "Market Data",
    href: "/market-data",
    icon: "TrendingUp",
    permission: Permission.PRICES_READ,
  },

  // Settings
  {
    label: "Settings",
    href: "/settings",
    icon: "Settings",
  },
];
