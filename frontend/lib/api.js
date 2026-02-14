// Shared API helpers for frontend components.
// Keep secret handling explicit: only send auth header when a key is configured.

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export function isDemoMode() {
  return DEMO_MODE;
}

function getDemoPath(path) {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  if (cleanPath.startsWith("/search")) return "/demo/search.json";
  if (cleanPath.startsWith("/metadata")) return "/demo/metadata.json";
  if (cleanPath.startsWith("/catalog/batch")) return "/demo/catalog_batch.json";

  const personMatch = cleanPath.match(/^\/person\/(\d+)/);
  if (personMatch) return `/demo/person_${personMatch[1]}.json`;

  const catalogStatusMatch = cleanPath.match(/^\/catalog\/(\d+)\/derived_status/);
  if (catalogStatusMatch) return `/demo/catalog_${catalogStatusMatch[1]}_derived_status.json`;

  const catalogContentMatch = cleanPath.match(/^\/catalog\/(\d+)\/content/);
  if (catalogContentMatch) return `/demo/catalog_${catalogContentMatch[1]}_content.json`;

  return null;
}

// Route read-only API calls to local JSON fixtures in demo mode.
export function buildApiUrl(path) {
  if (DEMO_MODE) {
    const demoPath = getDemoPath(path);
    // Use relative fixture paths so static demo works at both "/" and "/<repo>".
    if (demoPath) return `.${demoPath}`;
  }
  return `${API_BASE_URL}${path}`;
}

export function getApiHeaders({ useAuth = false, json = false } = {}) {
  const headers = {};

  if (json) {
    headers["Content-Type"] = "application/json";
  }

  // Demo mode never needs auth headers because it reads local fixture JSON.
  if (useAuth && !DEMO_MODE) {
    const key = process.env.NEXT_PUBLIC_API_AUTH_KEY;
    if (key) headers["X-API-Key"] = key;
  }

  return headers;
}
