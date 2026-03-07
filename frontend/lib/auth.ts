"use client";

const ACCESS_KEY = "lexgraph_access_token";
const REFRESH_KEY = "lexgraph_refresh_token";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

/** Returns Authorization header value, or empty string if not logged in. */
export function bearerHeader(): string {
  const token = getAccessToken();
  return token ? `Bearer ${token}` : "";
}
