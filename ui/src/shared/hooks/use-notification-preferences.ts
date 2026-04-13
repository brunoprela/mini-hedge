"use client";

import { useCallback, useEffect, useState } from "react";

export interface NotificationPreferences {
  /** Category toggles */
  orders: boolean;
  compliance: boolean;
  eod: boolean;
  marketData: boolean;
  system: boolean;
  /** Delivery channel toggles */
  inAppToasts: boolean;
  email: boolean;
  browserPush: boolean;
}

const STORAGE_KEY = "mini-hedge:notification-preferences";

const DEFAULT_PREFERENCES: NotificationPreferences = {
  orders: true,
  compliance: true,
  eod: true,
  marketData: false,
  system: true,
  inAppToasts: true,
  email: false,
  browserPush: false,
};

function loadPreferences(): NotificationPreferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_PREFERENCES;
    return { ...DEFAULT_PREFERENCES, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function savePreferences(prefs: NotificationPreferences) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // localStorage may be unavailable
  }
}

export function useNotificationPreferences() {
  const [preferences, setPreferences] = useState<NotificationPreferences>(DEFAULT_PREFERENCES);

  useEffect(() => {
    setPreferences(loadPreferences());
  }, []);

  const update = useCallback((partial: Partial<NotificationPreferences>) => {
    setPreferences((prev) => {
      const next = { ...prev, ...partial };
      savePreferences(next);
      return next;
    });
  }, []);

  return { preferences, update };
}
