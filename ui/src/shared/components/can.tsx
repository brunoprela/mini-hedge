"use client";

import type { Permission } from "@/shared/lib/permissions";
import { usePermission } from "@/shared/hooks/use-permission";
import type { ReactNode } from "react";

interface CanProps {
  permission: Permission | Permission[];
  mode?: "all" | "any";
  fallback?: ReactNode;
  children: ReactNode;
}

export function Can({
  permission,
  mode = "all",
  fallback = null,
  children,
}: CanProps) {
  const { can, canAll } = usePermission();

  const perms = Array.isArray(permission) ? permission : [permission];
  const allowed =
    mode === "all" ? canAll(perms) : perms.some((p) => can(p));

  return allowed ? <>{children}</> : <>{fallback}</>;
}
