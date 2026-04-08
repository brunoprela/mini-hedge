"use client";

import { TCAOrderDetail } from "@/features/tca/components/tca-order-detail";

export function TCAOrderDetailClient({ orderId }: { orderId: string }) {
  return (
    <div className="space-y-3">
      <h1 className="text-sm font-semibold">Transaction Cost Analysis</h1>
      <TCAOrderDetail orderId={orderId} />
    </div>
  );
}
