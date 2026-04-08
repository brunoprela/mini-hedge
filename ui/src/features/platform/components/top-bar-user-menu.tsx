"use client";

import { LogOut } from "lucide-react";
import Link from "next/link";
import { signOut } from "next-auth/react";
import { useEffect, useRef, useState } from "react";
import { useFundContext } from "@/shared/hooks/use-fund-context";

export function TopBarUserMenu({ userName, userInitials }: { userName: string; userInitials: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { fundSlug } = useFundContext();

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const handleLogout = async () => {
    const issuer = process.env.NEXT_PUBLIC_KEYCLOAK_ISSUER ?? "";
    const clientId = process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ?? "";
    const logoutUrl = `${issuer}/protocol/openid-connect/logout`;
    const redirectUri = encodeURIComponent(`${window.location.origin}/login`);
    await signOut({ redirect: false });
    window.location.href = `${logoutUrl}?post_logout_redirect_uri=${redirectUri}&client_id=${clientId}`;
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--primary)] text-[10px] font-bold text-white transition-opacity hover:opacity-80"
        title={userName}
      >
        {userInitials}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 min-w-[180px] rounded-md border border-[var(--border)] bg-[var(--background-raised)] py-1 shadow-xl">
          <div className="border-b border-[var(--border)] px-3 py-2">
            <p className="text-xs font-medium text-[var(--foreground)]">{userName}</p>
            <p className="text-[10px] text-[var(--muted-foreground)]">Manager</p>
          </div>
          <Link
            href={`/${fundSlug}/settings`}
            onClick={() => setOpen(false)}
            className="block px-3 py-1.5 text-xs text-[var(--foreground)] transition-colors hover:bg-[var(--muted)]"
          >
            Settings
          </Link>
          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-[var(--destructive)] transition-colors hover:bg-[var(--muted)]"
          >
            <LogOut className="h-3 w-3" />
            Logout
          </button>
        </div>
      )}
    </div>
  );
}
