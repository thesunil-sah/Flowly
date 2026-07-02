// Token storage. Access token lives in memory (re-minted from the refresh
// token). The refresh token goes to localStorage when "remember me" is checked
// (survives browser restart) or sessionStorage otherwise (this session only).
// All window access is guarded so this module is safe to import during SSR.

const REFRESH_KEY = "flowly.refresh";

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return (
    window.localStorage.getItem(REFRESH_KEY) ?? window.sessionStorage.getItem(REFRESH_KEY)
  );
}

/**
 * Store tokens. Pass `remember` on an explicit login to choose persistence;
 * omit it during a silent refresh to keep the token in its current store.
 */
export function setTokens(access: string, refresh: string, remember?: boolean): void {
  accessToken = access;
  if (typeof window === "undefined") return;

  if (remember === undefined) {
    // Silent refresh: keep the refresh token wherever it already lives.
    if (window.localStorage.getItem(REFRESH_KEY) !== null) {
      window.localStorage.setItem(REFRESH_KEY, refresh);
    } else {
      window.sessionStorage.setItem(REFRESH_KEY, refresh);
    }
    return;
  }

  const primary = remember ? window.localStorage : window.sessionStorage;
  const other = remember ? window.sessionStorage : window.localStorage;
  primary.setItem(REFRESH_KEY, refresh);
  other.removeItem(REFRESH_KEY);
}

export function clearTokens(): void {
  accessToken = null;
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(REFRESH_KEY);
  window.sessionStorage.removeItem(REFRESH_KEY);
}
