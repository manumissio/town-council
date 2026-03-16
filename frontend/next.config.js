/** @type {import('next').NextConfig} */
const staticExport = process.env.STATIC_EXPORT === "true";
const repositoryName = (process.env.GITHUB_REPOSITORY || "manumissio/town-council").split("/")[1];
const pagesBasePath = `/${repositoryName}`;
const appEnv = (process.env.APP_ENV || "dev").trim().toLowerCase();
const publicApiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

if (!staticExport && appEnv !== "dev" && publicApiUrl === "http://localhost:8000") {
  throw new Error("NEXT_PUBLIC_API_URL must be set to a non-localhost origin when APP_ENV is not dev.");
}

const securityHeaders = [
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
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
