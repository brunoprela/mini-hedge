import type { ReactNode } from "react";
import { TopNav } from "@/features/platform/components/top-nav";
import { Breadcrumbs } from "@/shared/components/breadcrumbs";
import { RealtimeProvider } from "@/shared/components/realtime-provider";
import { RealtimeToasts } from "@/shared/components/realtime-toasts";

export default function FundLayout({ children }: { children: ReactNode }) {
  return (
    <RealtimeProvider>
      <RealtimeToasts />
      <div className="flex h-screen flex-col bg-[var(--background)]">
        <TopNav />
        <main className="flex-1 overflow-y-auto px-4 py-3">
          <Breadcrumbs />
          {children}
        </main>
      </div>
    </RealtimeProvider>
  );
}
