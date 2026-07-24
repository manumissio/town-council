import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const NEXT_VERSION = "16.2.11";
const PATCHED_SHARP_VERSION = "0.35.3";
const ROOT_DEPENDENCY_SECTIONS = [
  "dependencies",
  "devDependencies",
  "optionalDependencies",
  "peerDependencies",
];
const packageManifest = JSON.parse(
  fs.readFileSync(path.resolve(process.cwd(), "package.json"), "utf8"),
);
const packageLock = JSON.parse(
  fs.readFileSync(path.resolve(process.cwd(), "package-lock.json"), "utf8"),
);

test("keeps Sharp transitive and pins the patched Next.js child", () => {
  assert.equal(packageManifest.dependencies.next, NEXT_VERSION);
  for (const dependencySectionName of ROOT_DEPENDENCY_SECTIONS) {
    assert.equal(
      packageManifest[dependencySectionName]?.sharp,
      undefined,
      `${dependencySectionName} must not declare Sharp`,
    );
  }
  assert.equal(
    packageManifest.overrides?.next?.sharp,
    PATCHED_SHARP_VERSION,
  );
});

test("locks patched Sharp without changing Next.js", () => {
  assert.equal(packageLock.packages["node_modules/next"].version, NEXT_VERSION);
  assert.equal(
    packageLock.packages["node_modules/sharp"].version,
    PATCHED_SHARP_VERSION,
  );
});
