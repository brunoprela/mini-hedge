"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { portfoliosQueryOptions } from "@/features/portfolio/api";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { processRedemption, processSubscription } from "../api";

type ActionType = "subscription" | "redemption";

interface Props {
  investorId: string;
  investorName: string;
  actionType: ActionType;
  onClose: () => void;
}

export function CapitalActionDialog({ investorId, investorName, actionType, onClose }: Props) {
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const [amount, setAmount] = useState("");
  const [navPerShare, setNavPerShare] = useState("");
  const [businessDate, setBusinessDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [portfolioId, setPortfolioId] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [shareClass, setShareClass] = useState("default");
  const [notes, setNotes] = useState("");

  const { data: portfolios } = useQuery(portfoliosQueryOptions(fundSlug));

  const mutation = useMutation({
    mutationFn: () => {
      const payload = {
        investor_id: investorId,
        amount,
        nav_per_share: navPerShare,
        business_date: businessDate,
        portfolio_id: portfolioId || null,
        currency,
        notes: notes || null,
        ...(actionType === "subscription" ? { share_class: shareClass } : {}),
      };

      return actionType === "subscription"
        ? processSubscription(fundSlug, payload)
        : processRedemption(fundSlug, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["investors"] });
      queryClient.invalidateQueries({ queryKey: ["capital-accounts"] });
      queryClient.invalidateQueries({ queryKey: ["capital-overview"] });
      queryClient.invalidateQueries({ queryKey: ["investor-history"] });
      queryClient.invalidateQueries({ queryKey: ["investor-transactions"] });
      toast.success(
        `${actionType === "subscription" ? "Subscription" : "Redemption"} processed for ${investorName}`,
      );
      onClose();
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const canSubmit =
    Number(amount) > 0 && Number(navPerShare) > 0 && businessDate && !mutation.isPending;

  const isSubscription = actionType === "subscription";
  const title = isSubscription ? "New Subscription" : "New Redemption";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-md border border-[var(--border)] bg-[var(--background)] p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            &times;
          </button>
        </div>

        <p className="mb-4 text-sm text-[var(--muted-foreground)]">{investorName}</p>

        {/* Amount */}
        <div className="mb-4">
          <label htmlFor="ca-amount" className="mb-1 block text-sm text-[var(--muted-foreground)]">
            Amount
          </label>
          <input
            id="ca-amount"
            type="number"
            min="0"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 font-mono text-sm"
          />
        </div>

        {/* NAV per Share */}
        <div className="mb-4">
          <label htmlFor="ca-nav" className="mb-1 block text-sm text-[var(--muted-foreground)]">
            NAV per Share
          </label>
          <input
            id="ca-nav"
            type="number"
            min="0"
            step="0.01"
            value={navPerShare}
            onChange={(e) => setNavPerShare(e.target.value)}
            placeholder="0.00"
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 font-mono text-sm"
          />
        </div>

        {/* Business Date */}
        <div className="mb-4">
          <label htmlFor="ca-date" className="mb-1 block text-sm text-[var(--muted-foreground)]">
            Business Date
          </label>
          <input
            id="ca-date"
            type="date"
            value={businessDate}
            onChange={(e) => setBusinessDate(e.target.value)}
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          />
        </div>

        {/* Portfolio */}
        <div className="mb-4">
          <label
            htmlFor="ca-portfolio"
            className="mb-1 block text-sm text-[var(--muted-foreground)]"
          >
            Portfolio (optional)
          </label>
          <select
            id="ca-portfolio"
            value={portfolioId}
            onChange={(e) => setPortfolioId(e.target.value)}
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          >
            <option value="">None</option>
            {portfolios?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        {/* Currency */}
        <div className="mb-4">
          <label
            htmlFor="ca-currency"
            className="mb-1 block text-sm text-[var(--muted-foreground)]"
          >
            Currency
          </label>
          <select
            id="ca-currency"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          >
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
            <option value="GBP">GBP</option>
            <option value="JPY">JPY</option>
            <option value="CHF">CHF</option>
          </select>
        </div>

        {/* Share Class (subscription only) */}
        {isSubscription && (
          <div className="mb-4">
            <label
              htmlFor="ca-share-class"
              className="mb-1 block text-sm text-[var(--muted-foreground)]"
            >
              Share Class
            </label>
            <input
              id="ca-share-class"
              type="text"
              value={shareClass}
              onChange={(e) => setShareClass(e.target.value)}
              placeholder="default"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
            />
          </div>
        )}

        {/* Notes */}
        <div className="mb-4">
          <label htmlFor="ca-notes" className="mb-1 block text-sm text-[var(--muted-foreground)]">
            Notes (optional)
          </label>
          <textarea
            id="ca-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            placeholder="Optional notes..."
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          />
        </div>

        {/* Shares preview */}
        {Number(amount) > 0 && Number(navPerShare) > 0 && (
          <p className="mb-4 text-sm text-[var(--muted-foreground)]">
            Shares:{" "}
            <span className="font-mono font-medium">
              {(Number(amount) / Number(navPerShare)).toLocaleString("en-US", {
                maximumFractionDigits: 4,
              })}
            </span>
          </p>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-md border border-[var(--border)] py-2 text-sm"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={!canSubmit}
            className={`flex-1 rounded-md py-2 text-sm font-medium text-white transition-colors ${
              isSubscription
                ? "bg-[var(--success)] hover:brightness-110 disabled:opacity-50"
                : "bg-[var(--destructive)] hover:brightness-110 disabled:opacity-50"
            }`}
          >
            {mutation.isPending
              ? "Processing..."
              : isSubscription
                ? "Process Subscription"
                : "Process Redemption"}
          </button>
        </div>
      </div>
    </div>
  );
}
