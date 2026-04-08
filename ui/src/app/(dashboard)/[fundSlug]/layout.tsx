import type { ReactNode } from "react";
import { Sidebar } from "@/features/platform/components/sidebar";
import { TopBar } from "@/features/platform/components/top-bar";
import { Breadcrumbs } from "@/shared/components/breadcrumbs";
import { RealtimeProvider } from "@/shared/components/realtime-provider";
import { RealtimeToasts } from "@/shared/components/realtime-toasts";
import { TradeTicketPanel } from "@/shared/components/trade-ticket-panel";
import { TradeTicketProvider } from "@/shared/components/trade-ticket-provider";

export default function FundLayout({ children }: { children: ReactNode }) {
  return (
    <RealtimeProvider>
      <RealtimeToasts />
      <TradeTicketProvider>
        <div className="flex h-screen bg-[var(--background)]">
          {/* Left sidebar */}
          <Sidebar />

          {/* Main area */}
          <div className="flex min-w-0 flex-1 flex-col">
            <TopBar />
            <main className="flex-1 overflow-y-auto px-4 py-3">
              <Breadcrumbs />
              {children}
            </main>
          </div>

          {/* Right trade ticket panel (conditional) */}
          <TradeTicketPanel />
        </div>
      </TradeTicketProvider>
    </RealtimeProvider>
  );
}
