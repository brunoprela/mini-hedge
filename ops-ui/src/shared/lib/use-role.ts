"use client";

import { useSession } from "next-auth/react";

export function useRole() {
  const { data: session } = useSession();
  return {
    role: session?.platformRole ?? "ops_viewer",
    isAdmin: session?.platformRole === "ops_admin",
  };
}
