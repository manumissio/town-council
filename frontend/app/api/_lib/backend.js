const BLOCKED_FETCH_SITES = new Set(["cross-site", "same-site"]);
const CROSS_SITE_DETAIL = "Cross-site mutation requests are not allowed.";
const FETCH_SITE_HEADER = "sec-fetch-site";
const FORBIDDEN_STATUS = 403;
const FORWARDED_PROTOCOL_HEADER = "x-forwarded-proto";
const HOST_HEADER = "host";
const INVALID_HOST_AUTHORITY = /[/\\?#]/;
const MUTATION_METHOD = "POST";
const ORIGIN_HEADER = "origin";
const WEB_PROTOCOLS = new Set(["http", "https"]);

function getInternalApiBaseUrl() {
  return process.env.INTERNAL_API_BASE_URL || "http://api:8000";
}

function getApiAuthKey() {
  const apiAuthKey = process.env.API_AUTH_KEY;
  if (!apiAuthKey) {
    throw new Error("API_AUTH_KEY is required for frontend backend proxy routes.");
  }
  return apiAuthKey;
}

function parseUrl(urlValue) {
  try {
    return new URL(urlValue);
  } catch (error) {
    if (!(error instanceof TypeError)) {
      throw error;
    }
    return null;
  }
}

function parseWebOrigin(originValue) {
  const parsedOrigin = parseUrl(originValue);
  const protocol = parsedOrigin?.protocol.slice(0, -1);
  return parsedOrigin && WEB_PROTOCOLS.has(protocol)
    ? parsedOrigin.origin
    : null;
}

function parseSerializedOrigin(originValue) {
  const parsedOrigin = parseWebOrigin(originValue);
  return parsedOrigin === originValue ? parsedOrigin : null;
}

function parseHostAuthority(hostValue, protocol) {
  if (
    hostValue !== hostValue.trim() ||
    INVALID_HOST_AUTHORITY.test(hostValue)
  ) {
    return null;
  }

  const parsedHost = parseUrl(`${protocol}://${hostValue}`);
  if (
    !parsedHost ||
    parsedHost.username ||
    parsedHost.password ||
    parsedHost.pathname !== "/" ||
    parsedHost.search ||
    parsedHost.hash
  ) {
    return null;
  }
  return parsedHost.host;
}

function getExternalRequestOrigin(request) {
  const requestUrl = new URL(request.url);
  const forwardedProtocolHeader = request.headers.get(
    FORWARDED_PROTOCOL_HEADER,
  );
  const protocol =
    forwardedProtocolHeader === null
      ? requestUrl.protocol.slice(0, -1)
      : forwardedProtocolHeader.split(",", 1)[0].trim().toLowerCase();
  if (!WEB_PROTOCOLS.has(protocol)) {
    return null;
  }
  const hostHeader = request.headers.get(HOST_HEADER);
  const host =
    hostHeader === null
      ? requestUrl.host
      : parseHostAuthority(hostHeader, protocol);
  if (host === null) {
    return null;
  }
  return parseWebOrigin(`${protocol}://${host}`);
}

function isNonSameOriginMutation(request, method) {
  if (method !== MUTATION_METHOD && request?.method !== MUTATION_METHOD) {
    return false;
  }

  if (BLOCKED_FETCH_SITES.has(request.headers.get(FETCH_SITE_HEADER))) {
    return true;
  }

  const externalRequestOrigin = getExternalRequestOrigin(request);
  if (externalRequestOrigin === null) {
    return true;
  }

  const origin = request.headers.get(ORIGIN_HEADER);
  return (
    origin !== null &&
    parseSerializedOrigin(origin) !== externalRequestOrigin
  );
}

export function buildBackendUrl(path, searchParams) {
  const url = new URL(path, getInternalApiBaseUrl());
  if (searchParams) {
    url.search = searchParams.toString();
  }
  return url;
}

export async function proxyBackendJson({
  request,
  method,
  path,
  searchParams,
  body,
}) {
  if (isNonSameOriginMutation(request, method)) {
    return Response.json(
      { detail: CROSS_SITE_DETAIL },
      { status: FORBIDDEN_STATUS },
    );
  }

  let apiAuthKey;
  try {
    apiAuthKey = getApiAuthKey();
  } catch (error) {
    console.error("frontend_backend_proxy.missing_auth_env", error);
    return Response.json(
      { detail: "Frontend backend proxy is not configured." },
      { status: 500 },
    );
  }

  const headers = new Headers({
    "X-API-Key": apiAuthKey,
  });

  if (body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(buildBackendUrl(path, searchParams), {
    method,
    headers,
    body,
    cache: "no-store",
  });
  const text = await response.text();

  return new Response(text, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") || "application/json",
    },
  });
}
