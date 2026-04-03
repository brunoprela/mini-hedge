"use client";

import { useMemo } from "react";
import {
  hasAllPermissions,
  hasPermission,
  type Permission,
  resolvePermissions,
} from "@/shared/lib/permissions";
import { useFundContext } from "./use-fund-context";

export function usePermission() {
  const { role } = useFundContext();

  const permissions = useMemo(() => resolvePermissions(role ? [role] : []), [role]);

  return {
    permissions,
    can: (permission: Permission) => hasPermission(permissions, permission),
    canAll: (perms: Permission[]) => hasAllPermissions(permissions, perms),
    role,
  };
}
