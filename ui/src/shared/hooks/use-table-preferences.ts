"use client";

import { useCallback, useEffect, useState } from "react";

export type TableDensity = "compact" | "comfortable";

export interface TablePreferences {
  density: TableDensity;
  defaultSortKey: string;
  defaultSortDirection: "asc" | "desc";
}

const STORAGE_KEY = "mini-hedge:table-preferences";

const DEFAULT_PREFERENCES: TablePreferences = {
  density: "comfortable",
  defaultSortKey: "created_at",
  defaultSortDirection: "desc",
};

function loadPreferences(): TablePreferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_PREFERENCES;
    return { ...DEFAULT_PREFERENCES, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function savePreferences(prefs: TablePreferences) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // localStorage may be unavailable
  }
}

export function useTablePreferences() {
  const [preferences, setPreferences] = useState<TablePreferences>(DEFAULT_PREFERENCES);

  useEffect(() => {
    setPreferences(loadPreferences());
  }, []);

  const update = useCallback((partial: Partial<TablePreferences>) => {
    setPreferences((prev) => {
      const next = { ...prev, ...partial };
      savePreferences(next);
      return next;
    });
  }, []);

  return { preferences, update };
}
