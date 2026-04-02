import { Permission } from "./permissions";

export interface NavItem {
  label: string;
  href: string;
  icon: "LayoutDashboard" | "Briefcase" | "Search" | "TrendingUp";
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
