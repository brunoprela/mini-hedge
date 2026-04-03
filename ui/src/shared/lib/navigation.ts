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
    | "BarChart3";
  permission?: Permission;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "", icon: "LayoutDashboard" },
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
    label: "Exposure",
    href: "/exposure",
    icon: "BarChart3",
    permission: Permission.EXPOSURE_READ,
  },
  {
    label: "Compliance",
    href: "/compliance",
    icon: "ShieldCheck",
    permission: Permission.COMPLIANCE_READ,
  },
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
];
