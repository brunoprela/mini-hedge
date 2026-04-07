"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useFundContext } from "@/shared/hooks/use-fund-context";
import { clientFetch } from "@/shared/lib/api";

interface ViolationItem {
  id: string;
  severity: string;
}

interface OrderItem {
  state: string;
}

interface EodStatus {
  id: string;
  status: string;
  run_date: string;
}

interface RiskSnapshot {
  id: string;
  var_95_1d: string;
}

interface Step {
  id: string;
  label: string;
  status: "done" | "warning" | "action" | "pending";
  detail: string;
  href: string;
}

export function WorkflowStepper() {
  const { fundSlug } = useFundContext();

  const { data: violations } = useQuery({
    queryKey: ["violations-all", fundSlug],
    queryFn: () =>
      clientFetch<ViolationItem[]>("/compliance/violations", { fundSlug }),
    staleTime: 60_000,
  });

  const { data: orders } = useQuery({
    queryKey: ["orders-all", fundSlug],
    queryFn: () => clientFetch<OrderItem[]>("/orders", { fundSlug }),
    staleTime: 30_000,
  });

  const { data: eodRuns } = useQuery({
    queryKey: ["eod-runs", fundSlug],
    queryFn: () => clientFetch<EodStatus[]>("/eod/runs", { fundSlug }),
    staleTime: 120_000,
  });

  const violationCount = violations?.length ?? 0;
  const pendingOrders =
    orders?.filter((o) => o.state === "pending" || o.state === "partially_filled")
      .length ?? 0;
  const filledToday =
    orders?.filter((o) => o.state === "filled").length ?? 0;

  const today = new Date().toISOString().slice(0, 10);
  const todayEod = eodRuns?.find((r) => r.run_date === today);
  const eodDone = todayEod?.status === "completed";
  const eodFailed = todayEod?.status === "failed";

  const steps: Step[] = [
    {
      id: "risk",
      label: "1. Check Risk",
      status: "done",
      detail: "Review risk metrics",
      href: `/${fundSlug}/risk`,
    },
    {
      id: "compliance",
      label: "2. Compliance",
      status:
        violationCount > 0
          ? "action"
          : "done",
      detail:
        violationCount > 0
          ? `${violationCount} violation${violationCount > 1 ? "s" : ""}`
          : "All clear",
      href: `/${fundSlug}/compliance`,
    },
    {
      id: "trade",
      label: "3. Trade",
      status:
        pendingOrders > 0
          ? "warning"
          : filledToday > 0
            ? "done"
            : "pending",
      detail:
        pendingOrders > 0
          ? `${pendingOrders} pending`
          : filledToday > 0
            ? `${filledToday} filled`
            : "No orders",
      href: `/${fundSlug}/orders`,
    },
    {
      id: "eod",
      label: "4. EOD",
      status: eodDone ? "done" : eodFailed ? "action" : "pending",
      detail: eodDone ? "Complete" : eodFailed ? "Failed" : "Not run",
      href: `/${fundSlug}/eod`,
    },
  ];

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
        Daily Workflow
      </h3>
      <div className="flex items-start gap-2">
        {steps.map((step, idx) => (
          <div key={step.id} className="flex flex-1 items-start">
            <Link
              href={step.href}
              className="group flex flex-1 flex-col items-center gap-1.5 rounded-lg p-2 transition-colors hover:bg-[var(--muted)]"
            >
              <StepIndicator status={step.status} />
              <span className="text-center text-xs font-medium text-[var(--foreground)] group-hover:text-[var(--primary)]">
                {step.label}
              </span>
              <span
                className={`text-center text-[10px] ${
                  step.status === "action"
                    ? "font-medium text-[var(--destructive)]"
                    : step.status === "warning"
                      ? "font-medium text-[var(--warning)]"
                      : "text-[var(--muted-foreground)]"
                }`}
              >
                {step.detail}
              </span>
            </Link>
            {idx < steps.length - 1 && (
              <div className="mt-4 flex h-px flex-1 items-center">
                <div className="h-px w-full bg-[var(--border)]" />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function StepIndicator({ status }: { status: Step["status"] }) {
  const colors = {
    done: "border-[var(--success)] bg-[var(--success)]",
    warning: "border-[var(--warning)] bg-[var(--warning)]",
    action: "border-[var(--destructive)] bg-[var(--destructive)]",
    pending: "border-[var(--border)] bg-[var(--muted)]",
  };

  const icons = {
    done: (
      <svg className="h-3 w-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    ),
    warning: <span className="text-[8px] font-bold text-black">!</span>,
    action: <span className="text-[8px] font-bold text-white">!</span>,
    pending: <div className="h-1.5 w-1.5 rounded-full bg-[var(--muted-foreground)]" />,
  };

  return (
    <div
      className={`flex h-6 w-6 items-center justify-center rounded-full border-2 ${colors[status]}`}
    >
      {icons[status]}
    </div>
  );
}
