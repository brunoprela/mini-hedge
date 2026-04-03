import type { ReactNode } from "react";
import { Sidebar } from "@/features/platform/components/sidebar";
import { Header } from "@/features/platform/components/header";
import { RealtimeProvider } from "@/shared/components/realtime-provider";

export default function FundLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen">
      <RealtimeProvider />
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
