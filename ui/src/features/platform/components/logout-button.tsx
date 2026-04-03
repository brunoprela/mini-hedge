"use client";

import { LogOut } from "lucide-react";
import { signOut } from "next-auth/react";

export function LogoutButton() {
  const handleLogout = async () => {
    const issuer = process.env.NEXT_PUBLIC_KEYCLOAK_ISSUER ?? "";
    const clientId = process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ?? "";
    const logoutUrl = `${issuer}/protocol/openid-connect/logout`;
    const redirectUri = encodeURIComponent(`${window.location.origin}/login`);

    await signOut({ redirect: false });
    window.location.href = `${logoutUrl}?post_logout_redirect_uri=${redirectUri}&client_id=${clientId}`;
  };

  return (
    <button
      type="button"
      onClick={handleLogout}
      className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
    >
      <LogOut className="h-4 w-4" />
      Sign out
    </button>
  );
}
