/** @type {import('next').NextConfig} */
const staticExport = process.env.STATIC_EXPORT === "true";
const repositoryName = (process.env.GITHUB_REPOSITORY || "manumissio/town-council").split("/")[1];
const pagesBasePath = `/${repositoryName}`;
const cspEnforce = process.env.NEXT_CSP_ENFORCE === "true";
const cspHeaderName = cspEnforce
  ? "Content-Security-Policy"
  : "Content-Security-Policy-Report-Only";
const cspValue = [
  "default-src 'self'",
  "base-uri 'self'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  "style-src 'self' 'unsafe-inline'",
  "script-src 'self' 'unsafe-inline'",
  "connect-src 'self' https: http://localhost:8000 ws://localhost:8000 http://localhost:7700",
].join("; ");

const securityHeaders = [
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: cspHeaderName, value: cspValue },
];

const nextConfig = {
  // Keep Docker production behavior unchanged; only use static export for Pages demo builds.
  output: staticExport ? "export" : "standalone",
  basePath: staticExport ? pagesBasePath : "",
  assetPrefix: staticExport ? pagesBasePath : undefined,
  trailingSlash: staticExport,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

module.exports = nextConfig
