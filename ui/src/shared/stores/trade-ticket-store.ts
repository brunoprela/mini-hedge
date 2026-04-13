"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { AlgoType } from "@/features/orders/types";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface TradeTicketDefaults {
  instrument?: string;
  side?: "buy" | "sell";
  quantity?: string;
  portfolioId?: string;
}

export interface TradeTicketFormState {
  instrument: string;
  side: "buy" | "sell";
  quantity: string;
  price: string;
  /** Algo execution toggle */
  useAlgo: boolean;
  algoType: AlgoType;
  algoDuration: string;
  algoSlices: string;
  algoVisibleQty: string;
}

const DEFAULT_FORM: TradeTicketFormState = {
  instrument: "",
  side: "buy",
  quantity: "",
  price: "",
  useAlgo: false,
  algoType: "twap",
  algoDuration: "3600",
  algoSlices: "100",
  algoVisibleQty: "",
};

export interface TradeTicketState {
  /* panel visibility */
  isOpen: boolean;
  /* defaults passed when opening (e.g. from a position row) */
  defaults: TradeTicketDefaults;
  /* persisted form state that survives open/close cycles */
  formState: TradeTicketFormState;

  /* actions */
  openTradeTicket: (defaults?: TradeTicketDefaults) => void;
  closeTradeTicket: () => void;
  setFormField: <K extends keyof TradeTicketFormState>(
    key: K,
    value: TradeTicketFormState[K],
  ) => void;
  resetForm: () => void;
}

/* ------------------------------------------------------------------ */
/*  Store                                                              */
/* ------------------------------------------------------------------ */

export const useTradeTicketStore = create<TradeTicketState>()(
  persist(
    (set) => ({
      isOpen: false,
      defaults: {},
      formState: { ...DEFAULT_FORM },

      openTradeTicket: (d) =>
        set((state) => {
          // When defaults are provided, merge them into formState so the
          // inner component picks them up.  Otherwise keep existing form.
          const nextForm = d
            ? {
                ...state.formState,
                ...(d.instrument !== undefined && { instrument: d.instrument }),
                ...(d.side !== undefined && { side: d.side }),
                ...(d.quantity !== undefined && { quantity: d.quantity }),
              }
            : state.formState;

          return { isOpen: true, defaults: d ?? {}, formState: nextForm };
        }),

      closeTradeTicket: () => set({ isOpen: false }),

      setFormField: (key, value) =>
        set((state) => ({
          formState: { ...state.formState, [key]: value },
        })),

      resetForm: () => set({ formState: { ...DEFAULT_FORM } }),
    }),
    {
      name: "trade-ticket",
      storage: createJSONStorage(() =>
        typeof window !== "undefined" ? sessionStorage : ({
          getItem: () => null,
          setItem: () => {},
          removeItem: () => {},
        }),
      ),
      // Only persist the form state, not panel visibility
      partialize: (state) => ({
        formState: state.formState,
      }),
    },
  ),
);
