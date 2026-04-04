"use client";

import { usePathname, useRouter } from "next/navigation";
import { useFundContext } from "@/shared/hooks/use-fund-context";

export function FundSelector() {
  const { fundSlug, fundName, funds, isLoading } = useFundContext();
  const router = useRouter();
  const pathname = usePathname();

  if (isLoading || funds.length <= 1) {
    return (
      <span className="text-sm font-semibold text-[var(--foreground-bright)]">{fundName}</span>
    );
  }

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newSlug = e.target.value;
    const subPath = pathname.replace(`/${fundSlug}`, "");
    router.push(`/${newSlug}${subPath}`);
  };

  return (
    <select
      value={fundSlug}
      onChange={handleChange}
      className="rounded-lg border border-[var(--input-border)] bg-[var(--input)] px-3 py-1.5 text-sm text-[var(--foreground)] focus:border-[var(--primary)] focus:outline-none"
    >
      {funds.map((f) => (
        <option key={f.fund_slug} value={f.fund_slug}>
          {f.fund_name} ({f.role})
        </option>
      ))}
    </select>
  );
}
