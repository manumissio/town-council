// Shared API helpers for frontend components.
// Keep secret handling explicit: only send auth header when a key is configured.

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getApiHeaders({ useAuth = false, json = false } = {}) {
  const headers = {};

  if (json) {
    headers["Content-Type"] = "application/json";
  }

  if (useAuth) {
    const key = process.env.NEXT_PUBLIC_API_AUTH_KEY;
    if (key) headers["X-API-Key"] = key;
  }

  return headers;
}
