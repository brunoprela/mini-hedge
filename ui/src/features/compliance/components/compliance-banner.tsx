"use client";

import { useQuery } from "@tanstack/react-query";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { violationsQueryOptions } from "../api";

const SEVERITY_STYLES: Record<string, string> = {
  block: "border-[var(--destructive)] bg-[var(--destructive-muted)] text-[var(--destructive)]",
  warning: "border-[var(--warning)] bg-[var(--warning-muted)] text-[var(--warning)]",
  breach:
    "border-[var(--accent-orange)] bg-[var(--accent-orange-muted)] text-[var(--accent-orange)]",
};

export function ComplianceBanner({ portfolioId }: { portfolioId: string }) {
  const { fundSlug } = useFundContext();
  const { data: violations } = useQuery(violationsQueryOptions(fundSlug, portfolioId));

  if (!violations || violations.length === 0) return null;

  const blocks = violations.filter((v) => v.severity === "block");
  const warnings = violations.filter((v) => v.severity !== "block");
  const severity = blocks.length > 0 ? "block" : (warnings[0]?.severity ?? "warning");

  return (
    <div
      className={`rounded-lg border p-3 ${SEVERITY_STYLES[severity] ?? SEVERITY_STYLES.warning}`}
    >
      <p className="text-sm font-medium">
        {blocks.length > 0 ? `\u26A0 ${blocks.length} compliance violation(s)` : ""}
        {blocks.length > 0 && warnings.length > 0 ? " \u00B7 " : ""}
        {warnings.length > 0 ? `${warnings.length} warning(s)` : ""}
      </p>
      <ul className="mt-1 space-y-0.5 text-xs">
        {violations.slice(0, 5).map((v) => (
          <li key={v.id}>
            <span className="font-medium">{v.rule_name}:</span> {v.message}
          </li>
        ))}
        {violations.length > 5 && (
          <li className="text-[var(--muted-foreground)]">+{violations.length - 5} more...</li>
        )}
      </ul>
    </div>
  );
}
