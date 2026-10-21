// Shared API helpers for frontend components.
// Keep secret handling explicit: only send auth header when a key is configured.

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const TRENDS_DASHBOARD_ENABLED = process.env.NEXT_PUBLIC_FEATURE_TRENDS_DASHBOARD === "true";
const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

function extractErrorDetail(payload, fallback) {
  if (payload && typeof payload.detail === "string") return payload.detail;
  if (payload && typeof payload.error === "string") return payload.error;
  if (payload && typeof payload.reason === "string") return payload.reason;
  return fallback;
}

export async function readJsonResponse(response, actionLabel) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    if (response.ok) return {};
  }

  if (!response.ok) {
    const detail = extractErrorDetail(payload, response.statusText || "Request failed");
    throw new Error(`${actionLabel} failed (HTTP ${response.status}): ${detail}`);
  }

  return payload || {};
}

export function isDemoMode() {
  return DEMO_MODE;
}

function getDemoPath(path) {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  const routePath = cleanPath.split("?", 1)[0];
  if (routePath === "/search") return "/demo/search.json";
  if (routePath === "/metadata") return "/demo/metadata.json";
  if (routePath === "/catalog/batch") return "/demo/catalog_batch.json";

  const catalogStatusMatch = routePath.match(/^\/catalog\/(\d+)\/derived_status$/);
  if (catalogStatusMatch) return `/demo/catalog_${catalogStatusMatch[1]}_derived_status.json`;

  const catalogContentMatch = routePath.match(/^\/catalog\/(\d+)\/content$/);
  if (catalogContentMatch) return `/demo/catalog_${catalogContentMatch[1]}_content.json`;

  return null;
}

// Route read-only API calls to local JSON fixtures in demo mode.
export function buildApiUrl(path) {
  if (DEMO_MODE) {
    const demoPath = getDemoPath(path);
    // Use relative fixture paths so static demo works at both "/" and "/<repo>".
    if (demoPath) return `.${demoPath}`;
    throw new Error("This action is not available in the sample preview.");
  }
  return `${API_BASE_URL}${path}`;
}

export function buildProtectedCatalogApiUrl(path) {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  if (DEMO_MODE) {
    const demoPath = getDemoPath(cleanPath);
    if (demoPath) return `.${demoPath}`;
    throw new Error("This action is not available in the sample preview.");
  }
  return `/api${cleanPath}`;
}

export function getApiHeaders({ useAuth = false, json = false } = {}) {
  const headers = {};

  if (json) {
    headers["Content-Type"] = "application/json";
  }

  // Browser callers no longer attach mutation credentials directly.
  // Auth-required browser actions flow through same-origin route handlers instead.
  void useAuth;

  return headers;
}
