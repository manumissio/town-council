import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";

import { JSDOM } from "jsdom";
import nextSwc from "next/dist/build/swc/index.js";
import React from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { act } from "react-dom/test-utils";

const require = createRequire(import.meta.url);
const COMPONENT_INTERACTION_TIMEOUT_MS = 2_000;
const frontendModulePaths = [
  "components/ResultCard.js",
  "components/DataTable.js",
  "components/LineageTimeline.js",
  "components/ui/table.jsx",
  "lib/api.js",
  "lib/taskPolling.js",
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

function createDeferred() {
  let resolve;
  let reject;
  const promise = new Promise((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, reject, resolve };
}

function installDom() {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
    url: "http://localhost/",
  });
  const browserGlobalNames = ["window", "document", "navigator", "HTMLElement", "Node", "Event"];
  const previousDescriptors = new Map(
    browserGlobalNames.map((globalName) => [
      globalName,
      Object.getOwnPropertyDescriptor(globalThis, globalName),
    ]),
  );
  for (const globalName of browserGlobalNames) {
    Object.defineProperty(globalThis, globalName, {
      configurable: true,
      value: dom.window[globalName],
    });
  }
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const restoreDom = () => {
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
    for (const [globalName, previousDescriptor] of previousDescriptors) {
      if (previousDescriptor) Object.defineProperty(globalThis, globalName, previousDescriptor);
      else delete globalThis[globalName];
    }
    dom.window.close();
  };
  return { dom, restoreDom };
}

function jsonResponse(payload) {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    async json() {
      return payload;
    },
  };
}

async function flushAsyncWork() {
  await new Promise((resolve) => setImmediate(resolve));
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

test("unmount aborts the re-extraction completion refresh", {
  timeout: COMPONENT_INTERACTION_TIMEOUT_MS,
}, async (testContext) => {
  const ResultCard = compileResultCard(testContext);
  const { dom, restoreDom } = installDom();
  const canonicalRefreshStarted = createDeferred();
  let canonicalRequestCount = 0;
  let derivedStatusRequestCount = 0;
  const consoleErrors = [];
  testContext.mock.method(console, "error", (...errorArguments) => {
    consoleErrors.push(errorArguments);
  });
  testContext.mock.method(globalThis, "fetch", async (requestUrl, requestOptions = {}) => {
    const url = String(requestUrl);
    if (url.includes("/derived_status")) {
      derivedStatusRequestCount += 1;
      return jsonResponse({});
    }
    if (url.includes("/catalog/42/content")) {
      canonicalRequestCount += 1;
      if (canonicalRequestCount === 1) return jsonResponse({ content: "initial text" });
      canonicalRefreshStarted.resolve(requestOptions.signal);
      return await new Promise((_resolve, reject) => {
        requestOptions.signal.addEventListener(
          "abort",
          () => reject(requestOptions.signal.reason),
          { once: true },
        );
      });
    }
    if (url.startsWith("/api/extract/42")) return jsonResponse({ task_id: "task-42" });
    if (url.includes("/tasks/task-42")) {
      return jsonResponse({ status: "complete", result: { extracted: true } });
    }
    throw new Error(`Unexpected request: ${url}`);
  });

  const container = dom.window.document.getElementById("root");
  const root = createRoot(container);
  let rootMounted = true;
  testContext.after(async () => {
    if (rootMounted) await act(async () => root.unmount());
    restoreDom();
  });
  const hit = {
    catalog_id: 42,
    city: "Test City",
    content: "initial text",
    date: "2026-08-02",
    event_name: "Regular Meeting",
    id: 42,
    result_type: "meeting",
    summary: null,
    title: "Regular Meeting",
    topics: [],
  };

  await act(async () => {
    root.render(React.createElement(ResultCard, { hit }));
  });
  const expandButton = container.querySelector('button[title="Expand Document Text"]');
  assert.ok(expandButton);
  await act(async () => {
    expandButton.click();
    await flushAsyncWork();
  });
  const reextractButton = Array.from(container.querySelectorAll("button")).find(
    (button) => button.textContent.trim() === "Re-extract text",
  );
  assert.ok(reextractButton);

  let completionSignal;
  await act(async () => {
    reextractButton.click();
    completionSignal = await canonicalRefreshStarted.promise;
  });
  await act(async () => {
    root.unmount();
    rootMounted = false;
    await flushAsyncWork();
  });

  assert.equal(completionSignal.aborted, true);
  assert.deepEqual(consoleErrors, []);
  assert.equal(derivedStatusRequestCount, 1);
  assert.equal(container.textContent, "");
});
