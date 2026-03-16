import { NextResponse } from "next/server";

function resolveBrowserApiOrigin() {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (configured) return new URL(configured).origin;

  const appEnv = (process.env.APP_ENV || "dev").trim().toLowerCase();
  if (appEnv === "dev") return "http://localhost:8000";

  throw new Error("NEXT_PUBLIC_API_URL must be set when APP_ENV is not dev.");
}

export function proxy(request) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const apiOrigin = resolveBrowserApiOrigin();
  const cspHeader = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    "style-src 'self' 'unsafe-inline'",
    `connect-src 'self' ${apiOrigin}`,
    "img-src 'self' data: blob: https:",
    "font-src 'self' data:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
  const cspHeaderName =
    process.env.NEXT_CSP_ENFORCE === "true"
      ? "Content-Security-Policy"
      : "Content-Security-Policy-Report-Only";

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set(cspHeaderName, cspHeader);

  const response = NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });

  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set(cspHeaderName, cspHeader);

  return response;
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
