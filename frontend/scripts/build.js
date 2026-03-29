const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const staticExport = process.env.STATIC_EXPORT === "true";
const projectRoot = path.resolve(__dirname, "..");
const apiDir = path.join(projectRoot, "app", "api");
const apiBackupDir = path.join(projectRoot, "app", "__api_runtime_only");

function hideApiRoutesForStaticExport() {
  if (!staticExport || !fs.existsSync(apiDir)) return false;
  if (fs.existsSync(apiBackupDir)) {
    throw new Error(`Static export backup path already exists: ${apiBackupDir}`);
  }
  // Why this exists: Next export cannot include App Router API handlers, but the
  // runtime app still depends on them for same-origin proxy routes.
  fs.renameSync(apiDir, apiBackupDir);
  return true;
}

function restoreApiRoutesIfNeeded(hidden) {
  if (!hidden) return;
  if (fs.existsSync(apiDir)) {
    throw new Error(`Static export restore blocked because ${apiDir} already exists`);
  }
  fs.renameSync(apiBackupDir, apiDir);
}

const nextBin = require.resolve("next/dist/bin/next");
const nextArgs = ["build", ...process.argv.slice(2)];

let routesHidden = false;
let exitCode = 1;

try {
  routesHidden = hideApiRoutesForStaticExport();
  const result = spawnSync(process.execPath, [nextBin, ...nextArgs], {
    stdio: "inherit",
    cwd: projectRoot,
    env: process.env,
  });
  if (result.error) {
    throw result.error;
  }
  exitCode = result.status ?? 1;
} finally {
  restoreApiRoutesIfNeeded(routesHidden);
}

process.exit(exitCode);
