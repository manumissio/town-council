/** @type {import('next').NextConfig} */
const staticExport = process.env.STATIC_EXPORT === "true";
const repositoryName = (process.env.GITHUB_REPOSITORY || "manumissio/town-council").split("/")[1];
const pagesBasePath = `/${repositoryName}`;

const nextConfig = {
  // Keep Docker production behavior unchanged; only use static export for Pages demo builds.
  output: staticExport ? "export" : "standalone",
  basePath: staticExport ? pagesBasePath : "",
  assetPrefix: staticExport ? pagesBasePath : undefined,
  trailingSlash: staticExport,
}

module.exports = nextConfig
