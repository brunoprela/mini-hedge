"use client";

import { InvestorDetail } from "@/features/investors/components/investor-detail";

export function InvestorDetailPageClient({ investorId }: { investorId: string }) {
  return <InvestorDetail investorId={investorId} />;
}
