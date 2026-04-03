"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { createRule, updateRule } from "../api";
import type { RuleDefinition } from "../types";

const RULE_TYPES = [
  { value: "concentration_limit", label: "Concentration Limit" },
  { value: "sector_limit", label: "Sector Limit" },
  { value: "country_limit", label: "Country Limit" },
  { value: "restricted_list", label: "Restricted List" },
  { value: "short_selling", label: "Short Selling" },
] as const;

const SEVERITIES = ["block", "warning", "breach"] as const;

function buildParameters(
  ruleType: string,
  fields: {
    maxPct: string;
    sector: string;
    country: string;
    restrictedTickers: string;
    allowShort: boolean;
  },
): Record<string, unknown> {
  switch (ruleType) {
    case "concentration_limit":
      return { max_pct: Number(fields.maxPct) };
    case "sector_limit":
      return {
        max_pct: Number(fields.maxPct),
        ...(fields.sector ? { sector: fields.sector } : {}),
      };
    case "country_limit":
      return {
        max_pct: Number(fields.maxPct),
        ...(fields.country ? { country: fields.country } : {}),
      };
    case "restricted_list":
      return {
        restricted_instruments: fields.restrictedTickers
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      };
    case "short_selling":
      return { allow_short: fields.allowShort };
    default:
      return {};
  }
}

function parseParameters(
  ruleType: string,
  params: Record<string, unknown>,
): {
  maxPct: string;
  sector: string;
  country: string;
  restrictedTickers: string;
  allowShort: boolean;
} {
  const defaults = {
    maxPct: "",
    sector: "",
    country: "",
    restrictedTickers: "",
    allowShort: false,
  };
  switch (ruleType) {
    case "concentration_limit":
      return { ...defaults, maxPct: String(params.max_pct ?? "") };
    case "sector_limit":
      return {
        ...defaults,
        maxPct: String(params.max_pct ?? ""),
        sector: String(params.sector ?? ""),
      };
    case "country_limit":
      return {
        ...defaults,
        maxPct: String(params.max_pct ?? ""),
        country: String(params.country ?? ""),
      };
    case "restricted_list":
      return {
        ...defaults,
        restrictedTickers: Array.isArray(params.restricted_instruments)
          ? (params.restricted_instruments as string[]).join(", ")
          : "",
      };
    case "short_selling":
      return { ...defaults, allowShort: Boolean(params.allow_short) };
    default:
      return defaults;
  }
}

interface RuleFormDialogProps {
  rule?: RuleDefinition;
  onClose: () => void;
}

export function RuleFormDialog({ rule, onClose }: RuleFormDialogProps) {
  const isEdit = Boolean(rule);
  const { fundSlug } = useFundContext();
  const queryClient = useQueryClient();

  const [name, setName] = useState(rule?.name ?? "");
  const [ruleType, setRuleType] = useState(rule?.rule_type ?? "concentration_limit");
  const [severity, setSeverity] = useState(rule?.severity ?? "warning");

  const parsed = rule ? parseParameters(rule.rule_type, rule.parameters) : undefined;
  const [maxPct, setMaxPct] = useState(parsed?.maxPct ?? "");
  const [sector, setSector] = useState(parsed?.sector ?? "");
  const [country, setCountry] = useState(parsed?.country ?? "");
  const [restrictedTickers, setRestrictedTickers] = useState(parsed?.restrictedTickers ?? "");
  const [allowShort, setAllowShort] = useState(parsed?.allowShort ?? false);

  const mutation = useMutation({
    mutationFn: () => {
      const parameters = buildParameters(ruleType, {
        maxPct,
        sector,
        country,
        restrictedTickers,
        allowShort,
      });
      if (isEdit && rule) {
        return updateRule(fundSlug, rule.id, { name, severity, parameters });
      }
      return createRule(fundSlug, {
        name,
        rule_type: ruleType,
        severity,
        parameters,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["compliance-rules"] });
      toast.success(isEdit ? "Rule updated" : "Rule created");
      onClose();
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const inputClass =
    "w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm";
  const labelClass = "mb-1 block text-sm text-[var(--muted-foreground)]";

  function renderParameterFields() {
    switch (ruleType) {
      case "concentration_limit":
        return (
          <div>
            <label htmlFor="param-max-pct" className={labelClass}>
              Max % of NAV
            </label>
            <input
              id="param-max-pct"
              type="number"
              min="0"
              max="100"
              step="0.1"
              value={maxPct}
              onChange={(e) => setMaxPct(e.target.value)}
              placeholder="e.g. 5"
              className={inputClass}
            />
          </div>
        );
      case "sector_limit":
        return (
          <>
            <div>
              <label htmlFor="param-max-pct-sector" className={labelClass}>
                Max % of NAV
              </label>
              <input
                id="param-max-pct-sector"
                type="number"
                min="0"
                max="100"
                step="0.1"
                value={maxPct}
                onChange={(e) => setMaxPct(e.target.value)}
                placeholder="e.g. 25"
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="param-sector" className={labelClass}>
                Sector (optional)
              </label>
              <input
                id="param-sector"
                type="text"
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                placeholder="e.g. Technology"
                className={inputClass}
              />
            </div>
          </>
        );
      case "country_limit":
        return (
          <>
            <div>
              <label htmlFor="param-max-pct-country" className={labelClass}>
                Max % of NAV
              </label>
              <input
                id="param-max-pct-country"
                type="number"
                min="0"
                max="100"
                step="0.1"
                value={maxPct}
                onChange={(e) => setMaxPct(e.target.value)}
                placeholder="e.g. 30"
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="param-country" className={labelClass}>
                Country (optional)
              </label>
              <input
                id="param-country"
                type="text"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                placeholder="e.g. US"
                className={inputClass}
              />
            </div>
          </>
        );
      case "restricted_list":
        return (
          <div>
            <label htmlFor="param-tickers" className={labelClass}>
              Restricted Tickers (comma-separated)
            </label>
            <textarea
              id="param-tickers"
              value={restrictedTickers}
              onChange={(e) => setRestrictedTickers(e.target.value)}
              placeholder="e.g. TSLA, GME, AMC"
              rows={3}
              className={inputClass}
            />
          </div>
        );
      case "short_selling":
        return (
          <div className="flex items-center gap-2">
            <input
              id="param-allow-short"
              type="checkbox"
              checked={allowShort}
              onChange={(e) => setAllowShort(e.target.checked)}
              className="h-4 w-4 rounded border-[var(--border)]"
            />
            <label htmlFor="param-allow-short" className="text-sm">
              Allow short selling
            </label>
          </div>
        );
      default:
        return null;
    }
  }

  const canSubmit = name.trim().length > 0 && !mutation.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg border border-[var(--border)] bg-[var(--background)] p-6 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{isEdit ? "Edit Rule" : "New Rule"}</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            &times;
          </button>
        </div>

        <div className="space-y-4">
          {/* Name */}
          <div>
            <label htmlFor="rule-name" className={labelClass}>
              Name
            </label>
            <input
              id="rule-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Single Name Concentration"
              className={inputClass}
            />
          </div>

          {/* Rule type (create only) */}
          {!isEdit && (
            <div>
              <label htmlFor="rule-type" className={labelClass}>
                Rule Type
              </label>
              <select
                id="rule-type"
                value={ruleType}
                onChange={(e) => setRuleType(e.target.value)}
                className={inputClass}
              >
                {RULE_TYPES.map((rt) => (
                  <option key={rt.value} value={rt.value}>
                    {rt.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Severity */}
          <div>
            <label htmlFor="rule-severity" className={labelClass}>
              Severity
            </label>
            <select
              id="rule-severity"
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              className={inputClass}
            >
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
          </div>

          {/* Dynamic parameter fields */}
          {renderParameterFields()}

          {/* Buttons */}
          <div className="flex gap-2 pt-2">
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
              className="flex-1 rounded-md bg-[var(--foreground)] py-2 text-sm font-medium text-[var(--background)] transition-colors hover:opacity-90 disabled:opacity-50"
            >
              {mutation.isPending ? "Saving..." : isEdit ? "Save" : "Create"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
