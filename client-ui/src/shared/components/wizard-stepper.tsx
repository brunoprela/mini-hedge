"use client";

/**
 * WizardStepper — compact horizontal stepper for multi-step flows.
 * Pure presentational component; URL/state management lives in the parent.
 */

import { Check } from "lucide-react";

export interface WizardStep {
  id: string;
  label: string;
}

interface WizardStepperProps {
  steps: WizardStep[];
  currentStep: number;
  className?: string;
}

export function WizardStepper({ steps, currentStep, className = "" }: WizardStepperProps) {
  return (
    <ol className={`flex items-center gap-2 ${className}`} aria-label="Progress">
      {steps.map((step, idx) => {
        const isActive = idx === currentStep;
        const isComplete = idx < currentStep;
        return (
          <li key={step.id} className="flex items-center gap-2">
            <div
              className={`flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold transition-colors ${
                isComplete
                  ? "border-[var(--primary)] bg-[var(--primary)] text-[var(--primary-foreground)]"
                  : isActive
                    ? "border-[var(--primary)] bg-[var(--card)] text-[var(--primary)]"
                    : "border-[var(--border)] bg-[var(--card)] text-[var(--muted-foreground)]"
              }`}
              aria-current={isActive ? "step" : undefined}
            >
              {isComplete ? <Check size={14} /> : idx + 1}
            </div>
            <span
              className={`text-sm ${
                isActive
                  ? "font-medium text-[var(--foreground)]"
                  : isComplete
                    ? "text-[var(--foreground)]"
                    : "text-[var(--muted-foreground)]"
              }`}
            >
              {step.label}
            </span>
            {idx < steps.length - 1 && (
              <span
                className={`h-px w-8 ${isComplete ? "bg-[var(--primary)]" : "bg-[var(--border)]"}`}
                aria-hidden="true"
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
