"use client";

import {
  createContext,
  useCallback,
  useContext,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { useSites } from "@/hooks/useSites";
import type { Site } from "@/lib/api";

const STORAGE_KEY = "flowly.activeSite";

type SiteContextValue = {
  sites: Site[];
  activeSiteId: string | null;
  setActiveSiteId: (siteId: string) => void;
  isLoading: boolean;
};

const SiteContext = createContext<SiteContextValue | null>(null);

// SSR-safe read of the persisted selection: null on the server, the stored
// value on the client — no effect, no hydration mismatch.
function useStoredSiteId(): string | null {
  return useSyncExternalStore(
    () => () => {},
    () => window.localStorage.getItem(STORAGE_KEY),
    () => null,
  );
}

// One shared "which site am I looking at" for the whole dashboard (header
// switcher + every page), replacing the per-page <select> pickers.
export function SiteProvider({ children }: { children: ReactNode }) {
  const { data: sites = [], isLoading } = useSites();
  const stored = useStoredSiteId();
  const [selected, setSelected] = useState<string | null>(null);

  const setActiveSiteId = useCallback((siteId: string) => {
    setSelected(siteId);
    try {
      window.localStorage.setItem(STORAGE_KEY, siteId);
    } catch {
      // storage may be unavailable (private mode); selection still works in-memory
    }
  }, []);

  // In-session choice wins, then the persisted one; an id that no longer
  // exists (deleted site, other account) falls back to the first site rather
  // than rendering an empty dashboard.
  const candidate = selected ?? stored;
  const activeSiteId =
    candidate && sites.some((s) => s.site_id === candidate)
      ? candidate
      : (sites[0]?.site_id ?? null);

  return (
    <SiteContext.Provider value={{ sites, activeSiteId, setActiveSiteId, isLoading }}>
      {children}
    </SiteContext.Provider>
  );
}

export function useActiveSite(): SiteContextValue {
  const ctx = useContext(SiteContext);
  if (!ctx) throw new Error("useActiveSite must be used within SiteProvider");
  return ctx;
}
