import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const nextConfigPath = path.resolve(process.cwd(), "next.config.js");
const nextConfigSource = fs.readFileSync(nextConfigPath, "utf8");
const proxyPath = path.resolve(process.cwd(), "proxy.js");
const proxySource = fs.readFileSync(proxyPath, "utf8");

test("defines CSP report-only/enforce switch", () => {
  assert.match(proxySource, /NEXT_CSP_ENFORCE/);
  assert.match(proxySource, /Content-Security-Policy-Report-Only/);
  assert.match(proxySource, /Content-Security-Policy/);
});

test("defines global security headers for all routes", () => {
  assert.match(nextConfigSource, /async headers\(\)/);
  assert.match(nextConfigSource, /source:\s*"\/:path\*"/);
  assert.match(nextConfigSource, /X-Content-Type-Options/);
  assert.match(nextConfigSource, /X-Frame-Options/);
});
