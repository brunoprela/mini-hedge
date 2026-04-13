"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface Watchlist {
  id: string;
  name: string;
  tickers: string[];
}

export interface WatchlistState {
  watchlists: Watchlist[];
  activeWatchlistId: string | null;

  /* actions */
  createWatchlist: (name: string) => void;
  deleteWatchlist: (id: string) => void;
  renameWatchlist: (id: string, name: string) => void;
  addTicker: (watchlistId: string, ticker: string) => void;
  removeTicker: (watchlistId: string, ticker: string) => void;
  setActiveWatchlist: (id: string | null) => void;
}

/* ------------------------------------------------------------------ */
/*  Store                                                              */
/* ------------------------------------------------------------------ */

export const useWatchlistStore = create<WatchlistState>()(
  persist(
    (set) => ({
      watchlists: [],
      activeWatchlistId: null,

      createWatchlist: (name) =>
        set((state) => {
          const id = crypto.randomUUID();
          return {
            watchlists: [...state.watchlists, { id, name, tickers: [] }],
            activeWatchlistId: id,
          };
        }),

      deleteWatchlist: (id) =>
        set((state) => ({
          watchlists: state.watchlists.filter((w) => w.id !== id),
          activeWatchlistId:
            state.activeWatchlistId === id ? null : state.activeWatchlistId,
        })),

      renameWatchlist: (id, name) =>
        set((state) => ({
          watchlists: state.watchlists.map((w) =>
            w.id === id ? { ...w, name } : w,
          ),
        })),

      addTicker: (watchlistId, ticker) =>
        set((state) => ({
          watchlists: state.watchlists.map((w) =>
            w.id === watchlistId && !w.tickers.includes(ticker)
              ? { ...w, tickers: [...w.tickers, ticker] }
              : w,
          ),
        })),

      removeTicker: (watchlistId, ticker) =>
        set((state) => ({
          watchlists: state.watchlists.map((w) =>
            w.id === watchlistId
              ? { ...w, tickers: w.tickers.filter((t) => t !== ticker) }
              : w,
          ),
        })),

      setActiveWatchlist: (id) => set({ activeWatchlistId: id }),
    }),
    {
      name: "watchlists",
      storage: createJSONStorage(() =>
        typeof window !== "undefined"
          ? localStorage
          : {
              getItem: () => null,
              setItem: () => {},
              removeItem: () => {},
            },
      ),
    },
  ),
);
