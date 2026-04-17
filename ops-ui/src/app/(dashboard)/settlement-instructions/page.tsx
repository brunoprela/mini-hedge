"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import { FundPortfolioPicker } from "@/shared/components/fund-portfolio-picker";
import { ErrorState } from "@mini-hedge/ui";
import { TableSkeleton } from "@mini-hedge/ui";
import { api } from "@/shared/lib/api-client";

interface SWIFTMessages {
  instrument_id: string;
  mt103: string;
  mt210: string;
}

function CollapsiblePre({ label, content }: { label: string; content: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        {label}
      </button>
      {open && (
        <pre className="mt-1 max-h-48 overflow-auto rounded bg-[var(--muted)] p-2 text-[11px] font-mono whitespace-pre-wrap">
          {content}
        </pre>
      )}
    </div>
  );
}

export default function SettlementInstructionsPage() {
  const [fundSlug, setFundSlug] = useState("");
  const [portfolioId, setPortfolioId] = useState("");

  const enabled = !!portfolioId;

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["settlement-messages", portfolioId],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/api/v1/cash/{portfolio_id}/settlement-messages",
        { params: { path: { portfolio_id: portfolioId } } },
      );
      if (error) throw error;
      return data as unknown as SWIFTMessages[];
    },
    enabled,
  });

  return (
    <div>
      <h2 className="mb-6 text-xl font-semibold">Settlement Instructions</h2>

      <div className="mb-6">
        <FundPortfolioPicker
          fundSlug={fundSlug}
          onFundChange={setFundSlug}
          portfolioId={portfolioId}
          onPortfolioChange={setPortfolioId}
        />
      </div>

      {!portfolioId && (
        <p className="text-sm text-[var(--muted-foreground)]">
          Select a fund and portfolio to view settlement instructions.
        </p>
      )}

      {portfolioId && isLoading && <TableSkeleton rows={4} columns={3} />}

      {portfolioId && isError && (
        <ErrorState message={error.message} onRetry={refetch} />
      )}

      {portfolioId && !isLoading && !isError && (
        <div className="overflow-x-auto">
          {data && data.length > 0 ? (
            <table className="min-w-full divide-y divide-[var(--border)]">
              <thead>
                <tr>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">Instrument</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">MT103</th>
                  <th scope="col" className="px-3 py-2 text-left text-[10px] font-semibold whitespace-nowrap text-[var(--muted-foreground)]">MT210</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--table-border)]">
                {data.map((msg) => (
                  <tr key={msg.instrument_id} className="transition-colors hover:bg-[var(--table-row-hover)]">
                    <td className="px-3 py-2 text-sm font-mono align-top">{msg.instrument_id}</td>
                    <td className="px-3 py-2 text-sm align-top">
                      <CollapsiblePre label="MT103" content={msg.mt103} />
                    </td>
                    <td className="px-3 py-2 text-sm align-top">
                      <CollapsiblePre label="MT210" content={msg.mt210} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-[var(--muted-foreground)]">
              No pending settlement messages.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
