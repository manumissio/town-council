import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";

import nextSwc from "next/dist/build/swc/index.js";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const require = createRequire(import.meta.url);
const frontendModulePaths = [
  "components/ResultCard.js",
  "components/DataTable.js",
  "components/LineageTimeline.js",
  "components/ui/table.jsx",
  "lib/api.js",
  "lib/textFormatter.js",
  "lib/utils.js",
];
const externalDependencies = [
  "clsx",
  "isomorphic-dompurify",
  "lucide-react",
  "react",
  "react-dom",
  "tailwind-merge",
];

function linkModule(moduleSource, moduleTarget) {
  fs.mkdirSync(path.dirname(moduleTarget), { recursive: true });
  fs.symlinkSync(moduleSource, moduleTarget, "dir");
}

function configureModuleResolution(artifactRoot) {
  const artifactModules = path.join(artifactRoot, "node_modules");
  for (const dependencyName of externalDependencies) {
    linkModule(
      path.resolve(process.cwd(), "node_modules", dependencyName),
      path.join(artifactModules, dependencyName),
    );
  }
  linkModule(path.join(artifactRoot, "components"), path.join(artifactModules, "@/components"));
  linkModule(path.join(artifactRoot, "lib"), path.join(artifactModules, "@/lib"));
}

function compileResultCard(testContext) {
  const artifactRoot = fs.mkdtempSync(path.join(os.tmpdir(), "tc-result-card-render-"));
  testContext.after(() => fs.rmSync(artifactRoot, { recursive: true, force: true }));
  configureModuleResolution(artifactRoot);

  for (const frontendModulePath of frontendModulePaths) {
    const moduleSourcePath = path.resolve(process.cwd(), frontendModulePath);
    const compiledModulePath = path.join(
      artifactRoot,
      frontendModulePath.replace(/\.jsx$/, ".js"),
    );
    const compiledModule = nextSwc.transformSync(fs.readFileSync(moduleSourcePath, "utf8"), {
      filename: moduleSourcePath,
      jsc: {
        parser: { syntax: "ecmascript", jsx: true },
        transform: { react: { runtime: "automatic" } },
      },
      module: { type: "commonjs" },
    });
    fs.mkdirSync(path.dirname(compiledModulePath), { recursive: true });
    fs.writeFileSync(compiledModulePath, compiledModule.code, "utf8");
  }
  return require(path.join(artifactRoot, "components/ResultCard.js")).default;
}

test("people projection does not render meeting-card affordances", (testContext) => {
  const ResultCard = compileResultCard(testContext);
  const hit = {
    id: 42,
    catalog_id: 42,
    title: "Regular Meeting",
    city: "Test City",
    date: "2026-08-01",
    content: "Meeting content",
    result_type: "meeting",
    summary: null,
    topics: [],
    people_metadata: [{ id: 7, name: "Retired Projection Official" }],
  };

  const markup = renderToStaticMarkup(React.createElement(ResultCard, { hit }));

  assert.doesNotMatch(markup, /Retired Projection Official|Officials:|Verified public roster/);
});
