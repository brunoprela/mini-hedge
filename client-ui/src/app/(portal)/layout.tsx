import { MobileHeader } from "@/shared/components/mobile-header";
import { Sidebar } from "@/shared/components/sidebar";
import { MobileNavProvider } from "@/shared/lib/use-mobile-nav";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <MobileNavProvider>
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0 lg:ml-[var(--sidebar-width)]">
          <MobileHeader />
          <main className="flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
        </div>
      </div>
    </MobileNavProvider>
  );
}
