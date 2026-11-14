"use client";

const TOKEN_KEY = "spider-token";
const ORG_KEY = "spider-org-id";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getOrgId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ORG_KEY);
}

export function setOrgId(orgId: string | null) {
  if (typeof window === "undefined") return;
  if (orgId) localStorage.setItem(ORG_KEY, orgId);
  else localStorage.removeItem(ORG_KEY);
}

export function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const token = getAccessToken();
  const org = getOrgId();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (org) headers["X-Organization-Id"] = org;
  return headers;
}
