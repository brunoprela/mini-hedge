"use client";

import { useRouter, usePathname } from "next/navigation";
import { useFundContext } from "@/shared/hooks/use-fund-context";

export function FundSelector() {
  const { fundSlug, fundName, funds, isLoading } = useFundContext();
  const router = useRouter();
  const pathname = usePathname();

  if (isLoading || funds.length <= 1) {
    return (
      <span className="text-sm font-medium">{fundName}</span>
    );
  }

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newSlug = e.target.value;
    // Preserve the current sub-path when switching funds
    const subPath = pathname.replace(`/${fundSlug}`, "");
    router.push(`/${newSlug}${subPath}`);
  };

  return (
    <select
      value={fundSlug}
      onChange={handleChange}
      className="rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-sm"
    >
      {funds.map((f) => (
        <option key={f.fund_slug} value={f.fund_slug}>
          {f.fund_name} ({f.role})
        </option>
      ))}
    </select>
  );
}
