import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";

import { JSDOM } from "jsdom";
import nextSwc from "next/dist/build/swc/index.js";
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";

const require = createRequire(import.meta.url);
const COMPONENT_INTERACTION_TIMEOUT_MS = 2_000;
const frontendModulePaths = [
  "app/page.js",
  "components/SearchHub.js",
  "components/ui/tooltip.jsx",
  "state/search-state.js",
  "state/use-record-search.js",
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
  "clsx", "isomorphic-dompurify", "lucide-react", "react", "react-dom", "tailwind-merge", "@radix-ui/react-tooltip",
];
const TEST_MEETING_HIT = {
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

function compileResultCard(testContext, entryPath = "components/ResultCard.js") {
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
  return require(path.join(artifactRoot, entryPath)).default;
}

function createDeferred() {
  let resolve;
  const promise = new Promise((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
}

function installDom() {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
    url: "http://localhost/",
  });
  // React was imported before this DOM, so its legacy input-event bridge is active.
  dom.window.HTMLElement.prototype.attachEvent = () => {};
  dom.window.HTMLElement.prototype.detachEvent = () => {};
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

function findButton(container, label) {
  return Array.from(container.querySelectorAll("button")).find(
    (button) => button.textContent.trim() === label,
  );
}

async function mountRelatedRecord(testContext, relatedReplies) {
  const ResultCard = compileResultCard(testContext);
  const { dom, restoreDom } = installDom();
  testContext.mock.method(globalThis, "fetch", async (requestUrl) => {
    const url = String(requestUrl);
    if (url.includes("/catalog/batch?")) {
      const reply = relatedReplies.shift();
      if (reply instanceof Error) throw reply;
      return reply;
    }
    if (url.includes("/catalog/42/content")) return jsonResponse({ content: "Meeting source text" });
    if (url.includes("/catalog/42/derived_status")) return jsonResponse({});
    throw new Error(`Unexpected request: ${url}`);
  });
  function NavigationProbe() {
    const [selected, setSelected] = React.useState(null);
    return React.createElement(React.Fragment, null,
      React.createElement("output", null, selected ? `${selected.id}: ${selected.title}` : "No related record selected"),
      React.createElement(ResultCard, { hit: { ...TEST_MEETING_HIT, related_ids: [43] }, onRelatedMeetingClick: setSelected }),
    );
  }
  const container = dom.window.document.getElementById("root");
  const root = createRoot(container);
  testContext.after(async () => {
    await act(async () => root.unmount());
    restoreDom();
  });
  await act(async () => root.render(React.createElement(NavigationProbe)));
  await act(async () => {
    container.querySelector('button[title="Expand Document Text"]').click();
    await flushAsyncWork();
  });
  return container;
}

test("View selects the exact related record for its parent", async (testContext) => {
  const related = { id: 43, title: "Other business", date: "2026-01-01", city: "Other City" };
  const container = await mountRelatedRecord(testContext, [jsonResponse([related])]);

  await act(async () => findButton(container, "View").click());

  assert.equal(container.querySelector("output").textContent, "43: Other business");
});

test("related record read failure explains the error and retry recovers", async (testContext) => {
  const related = { id: 43, title: "Related hearing", date: "2026-01-01", city: "Other City" };
  const container = await mountRelatedRecord(testContext, [
    new TypeError("Related service unavailable"),
    jsonResponse([related]),
  ]);

  assert.ok(container.textContent.includes("Related service unavailable"));
  await act(async () => {
    findButton(container, "Retry related meetings").click();
    await flushAsyncWork();
  });
  assert.ok(container.textContent.includes("Related hearing"));
  await act(async () => findButton(container, "View").click());
  assert.equal(container.querySelector("output").textContent, "43: Related hearing");
});

test("a collapsed related read cannot replace the reopened record list", async (testContext) => {
  const oldRead = createDeferred();
  const reopenedRead = createDeferred();
  const container = await mountRelatedRecord(testContext, [oldRead.promise, reopenedRead.promise]);
  await act(async () => container.querySelector('button[title="Collapse Document"]').click());
  await act(async () => {
    container.querySelector('button[title="Expand Document Text"]').click();
    await flushAsyncWork();
    oldRead.resolve(jsonResponse([{ id: 43, title: "Obsolete related hearing" }]));
    await flushAsyncWork();
  });
  assert.equal(container.textContent.includes("Obsolete related hearing"), false);
  assert.equal(findButton(container, "View"), undefined);
  await act(async () => {
    reopenedRead.resolve(jsonResponse([{ id: 44, title: "Current related hearing" }]));
    await flushAsyncWork();
  });
  assert.ok(container.textContent.includes("Current related hearing"));
  assert.ok(findButton(container, "View"));
});

for (const scenario of [
  { name: "HTTP failure", reply: { ok: false, status: 503, statusText: "Service Unavailable", json: async () => ({ detail: "Related service unavailable" }) }, message: "Related service unavailable" },
  { name: "unreadable payload", reply: jsonResponse({ meetings: [] }), message: "Related meetings response is unreadable." },
  { name: "missing record identity", reply: jsonResponse([{ title: "Unknown record" }]), message: "Related meetings response is unreadable." },
  { name: "empty batch", reply: jsonResponse([]), message: "No related meetings are available." },
]) {
  test(`related meetings explain ${scenario.name} without a View action`, async (testContext) => {
    const container = await mountRelatedRecord(testContext, [scenario.reply]);
    assert.ok(container.textContent.includes(scenario.message));
    assert.equal(findButton(container, "View"), undefined);
  });
}

test("a selected related record opens its canonical content immediately", async (testContext) => {
  const ResultCard = compileResultCard(testContext);
  const { dom, restoreDom } = installDom();
  testContext.mock.method(globalThis, "fetch", async requestUrl => {
    if (String(requestUrl).includes("/content")) return jsonResponse({ content: "Canonical related hearing text" });
    if (String(requestUrl).includes("/derived_status")) return jsonResponse({});
    throw new Error(`Unexpected request: ${requestUrl}`);
  });
  const container = dom.window.document.getElementById("root");
  const root = createRoot(container);
  testContext.after(async () => {
    await act(async () => root.unmount());
    restoreDom();
  });
  await act(async () => {
    root.render(React.createElement(ResultCard, { hit: TEST_MEETING_HIT, initiallyExpanded: true }));
    await flushAsyncWork();
  });
  assert.ok(container.textContent.includes("Canonical related hearing text"));
});

test("home opens the batch record with separate catalog and event ownership, then returns to search", async (testContext) => {
  const Home = compileResultCard(testContext, "app/page.js");
  const { dom, restoreDom } = installDom();
  const related = {
    id: 43, event_id: 91, title: "Related budget hearing", filename: "related.pdf",
    date: "2026-01-01", city: "Other City", url: "https://example.org/related.pdf",
    summary: "Saved related budget business", topics: ["Budget"], related_ids: [],
  };
  let reportedEvent;
  testContext.mock.method(globalThis, "fetch", async (requestUrl, options) => {
    const url = String(requestUrl);
    if (url.endsWith("/metadata")) return jsonResponse({ cities: ["Test City"] });
    if (url.endsWith("/search/capabilities")) return jsonResponse({ semantic_enabled: false });
    if (url.includes("/search?")) return jsonResponse({ hits: [{ ...TEST_MEETING_HIT, related_ids: [43] }], estimatedTotalHits: 1 });
    if (url.includes("/catalog/batch?")) return jsonResponse([related]);
    if (url.includes("/catalog/42/content")) return jsonResponse({ content: "Original meeting source text" });
    if (url.includes("/catalog/43/content")) return jsonResponse({ content: "Canonical related budget source" });
    if (/\/catalog\/(42|43)\/derived_status$/.test(url)) return jsonResponse({});
    if (url === "/api/report-issue") {
      reportedEvent = JSON.parse(options.body).event_id;
      return jsonResponse({ detail: "Recorded" });
    }
    throw new Error(`Unexpected request: ${url}`);
  });
  const container = dom.window.document.getElementById("root");
  const root = createRoot(container);
  testContext.after(async () => { await act(async () => root.unmount()); restoreDom(); });
  await act(async () => root.render(React.createElement(Home)));
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 450)); });
  await act(async () => {
    container.querySelector('button[title="Expand Document Text"]').click();
    await flushAsyncWork();
  });
  const view = container.querySelector('button[aria-label="View related meeting: Related budget hearing"]');
  assert.ok(view, "Home must wire the existing related View action");
  await act(async () => { view.click(); await flushAsyncWork(); });
  assert.ok(container.textContent.includes("Canonical related budget source"));
  assert.equal(container.querySelector("h2").textContent, related.title);
  assert.equal(container.querySelector('a[title="Open source document"]').href, related.url);
  assert.equal(container.querySelector('input[type="search"]'), null);
  assert.equal(container.textContent.includes("Estimated matching records:"), false);
  await act(async () => container.querySelector('button[title="Report Data Error"]').click());
  await act(async () => { findButton(container, "Wrong City").click(); await flushAsyncWork(); });
  assert.equal(reportedEvent, related.event_id);
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 3100)); });
  await act(async () => { findButton(container, "Back to search results").click(); await flushAsyncWork(); });
  assert.ok(container.querySelector('input[type="search"]'));
  assert.ok(container.textContent.includes(TEST_MEETING_HIT.event_name));
  assert.equal(container.textContent.includes("Related budget hearing"), false);
});

test("meeting cards preserve calendar dates across viewer timezones", (testContext) => {
  const ResultCard = compileResultCard(testContext);
  const calendarDates = [
    ["2021-05-10", "May 10, 2021"],
    ["2020-05-27", "May 27, 2020"],
    ["2026-01-01", "January 1, 2026"],
    ["2024-02-29", "February 29, 2024"],
    [null, "Unknown Date"],
  ];

  for (const [date, displayedDate] of calendarDates) {
    const markup = renderToStaticMarkup(
      React.createElement(ResultCard, { hit: { ...TEST_MEETING_HIT, date } }),
    );
    assert.ok(markup.includes(displayedDate), `Expected calendar date: ${displayedDate}`);
  }
});

test("related meetings preserve their calendar dates across viewer timezones", async (testContext) => {
  const ResultCard = compileResultCard(testContext);
  const { dom, restoreDom } = installDom();
  const relatedMeetings = [
    { id: 43, title: "Related hearing", date: "2021-05-10", city: "Test City" },
    { id: 44, title: "Related workshop", date: "2020-05-27", city: "Test City" },
    { id: 45, title: "New year meeting", date: "2026-01-01", city: "Test City" },
    { id: 46, title: "Leap day meeting", date: "2024-02-29", city: "Test City" },
  ];
  testContext.mock.method(globalThis, "fetch", async (requestUrl) => {
    const url = String(requestUrl);
    if (url.includes("/catalog/batch?")) return jsonResponse(relatedMeetings);
    if (url.includes("/catalog/42/content")) return jsonResponse({ content: "Meeting source text" });
    if (url.includes("/catalog/42/derived_status")) return jsonResponse({});
    throw new Error(`Unexpected request: ${url}`);
  });
  const container = dom.window.document.getElementById("root");
  const root = createRoot(container);
  testContext.after(async () => {
    await act(async () => root.unmount());
    restoreDom();
  });
  await act(async () => {
    root.render(React.createElement(ResultCard, {
      hit: { ...TEST_MEETING_HIT, related_ids: relatedMeetings.map(meeting => meeting.id) },
    }));
  });
  await act(async () => {
    container.querySelector('button[title="Expand Document Text"]').click();
    await flushAsyncWork();
  });

  for (const displayedDate of ["May 10, 2021", "May 27, 2020", "Jan 1, 2026", "Feb 29, 2024"]) {
    assert.ok(container.textContent.includes(displayedDate), `Expected related date: ${displayedDate}`);
  }
});

test("people projection does not render meeting-card affordances", (testContext) => {
  const ResultCard = compileResultCard(testContext);
  const hit = {
    ...TEST_MEETING_HIT,
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
  await act(async () => {
    root.render(React.createElement(ResultCard, { hit: TEST_MEETING_HIT }));
  });
  const expandButton = container.querySelector('button[title="Expand Document Text"]');
  assert.ok(expandButton);
  await act(async () => {
    expandButton.click();
    await flushAsyncWork();
  });
  const reextractButton = findButton(container, "Re-extract text");
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
  assert.equal(derivedStatusRequestCount, 1);
});

const agendaScenarios = [
  {
    name: "renders populated task agenda items",
    taskItems: [{ order: 1, title: "Zoning appeal", description: "Public hearing" }],
    refreshedItems: null,
    expectedTitle: "Zoning appeal",
    expectedRefreshes: 0,
  },
  {
    name: "refreshes stored agenda items after an empty task result",
    taskItems: [],
    refreshedItems: [{ order: 1, title: "Persisted agenda item", description: "Stored row" }],
    expectedTitle: "Persisted agenda item",
    expectedRefreshes: 1,
  },
];

for (const summaryScenario of [
  { name: "stale", summary: "Saved summary", status: { summary_is_stale: true }, expected: "Stale" },
  { name: "partial", summary: "Summary covers first 2 of 5 agenda items", status: {}, expected: "Partial (2/5 items)" },
  { name: "blocked", summary: null, status: { summary_blocked_reason: "Insufficient source text" }, expected: "Summary blocked" },
]) {
  test(`summary tab explains ${summaryScenario.name} content`, async testContext => {
    const ResultCard = compileResultCard(testContext);
    const { restoreDom } = installDom();
    testContext.mock.method(globalThis, "fetch", async requestUrl => jsonResponse(
      String(requestUrl).includes("derived_status") ? summaryScenario.status : { content: "Synthetic source" },
    ));
    const container = document.getElementById("root");
    const root = createRoot(container);
    testContext.after(async () => { await act(async () => root.unmount()); restoreDom(); });
    await act(async () => root.render(React.createElement(ResultCard, { hit: { ...TEST_MEETING_HIT, summary: summaryScenario.summary } })));
    await act(async () => { container.querySelector('button[title="Expand Document Text"]').click(); await flushAsyncWork(); });
    await act(async () => findButton(container, "AI Summary").click());
    assert.ok(container.textContent.includes(summaryScenario.expected));
  });
}

test("pending summary task displays processing and disables generation", async testContext => {
  const ResultCard = compileResultCard(testContext);
  const { restoreDom } = installDom();
  testContext.mock.method(globalThis, "fetch", async requestUrl => {
    const url = String(requestUrl);
    if (url.startsWith("/api/summarize/")) return jsonResponse({ task_id: "pending-summary" });
    if (url.includes("/tasks/")) return jsonResponse({ status: "pending" });
    if (url.includes("derived_status")) return jsonResponse({ summary_not_generated_yet: true });
    return jsonResponse({ content: "Synthetic source" });
  });
  const container = document.getElementById("root");
  const root = createRoot(container);
  testContext.after(async () => { await act(async () => root.unmount()); restoreDom(); });
  await act(async () => root.render(React.createElement(ResultCard, { hit: TEST_MEETING_HIT })));
  await act(async () => { container.querySelector('button[title="Expand Document Text"]').click(); await flushAsyncWork(); });
  await act(async () => findButton(container, "AI Summary").click());
  await act(async () => { findButton(container, "Generate Local Summary").click(); await flushAsyncWork(); });
  assert.match(container.textContent, /Reading/);
  assert.equal(findButton(container, "Reading...").disabled, true);
});

test("missing sample summary explains that generation is unavailable", async testContext => {
  const previousDemoMode = process.env.NEXT_PUBLIC_DEMO_MODE;
  process.env.NEXT_PUBLIC_DEMO_MODE = "true";
  const ResultCard = compileResultCard(testContext);
  if (previousDemoMode === undefined) delete process.env.NEXT_PUBLIC_DEMO_MODE;
  else process.env.NEXT_PUBLIC_DEMO_MODE = previousDemoMode;
  const { restoreDom } = installDom();
  testContext.mock.method(globalThis, "fetch", async requestUrl => {
    assert.match(String(requestUrl), /^\.\/demo\//);
    return jsonResponse(String(requestUrl).includes("derived_status")
      ? { summary_not_generated_yet: true } : { content: "" });
  });
  const container = document.getElementById("root");
  const root = createRoot(container);
  testContext.after(async () => { await act(async () => root.unmount()); restoreDom(); });
  await act(async () => root.render(React.createElement(ResultCard, { hit: TEST_MEETING_HIT })));
  await act(async () => { container.querySelector('button[title="Expand Document Text"]').click(); await flushAsyncWork(); });
  await act(async () => findButton(container, "AI Summary").click());
  assert.match(container.textContent, /Missing summary is intentional in this sample/);
  assert.equal(findButton(container, "Generate Local Summary").disabled, true);
  assert.equal(container.querySelector('a[title="Open source document"]'), null);
});

test("unmount before enqueue completes cannot start polling", async testContext => {
  const ResultCard = compileResultCard(testContext);
  const { restoreDom } = installDom();
  const enqueue = createDeferred();
  const unexpectedRequests = [];
  testContext.mock.method(globalThis, "fetch", async requestUrl => {
    const url = String(requestUrl);
    if (url.startsWith("/api/summarize/")) return enqueue.promise;
    if (url.includes("derived_status")) return jsonResponse({ has_content: true });
    if (url.includes("/content")) return jsonResponse({ content: "Synthetic source" });
    unexpectedRequests.push(url);
    return jsonResponse({ status: "complete", result: {} });
  });
  const container = document.getElementById("root");
  const root = createRoot(container);
  testContext.after(restoreDom);
  await act(async () => root.render(React.createElement(ResultCard, { hit: { ...TEST_MEETING_HIT, summary: "Saved summary" } })));
  await act(async () => { container.querySelector('button[title="Expand Document Text"]').click(); await flushAsyncWork(); });
  await act(async () => findButton(container, "AI Summary").click());
  await act(async () => container.querySelector('button[title^="Regenerate the cached summary"]').click());
  await act(async () => root.unmount());
  await act(async () => { enqueue.resolve(jsonResponse({ task_id: "late-enqueue" })); await flushAsyncWork(); });
  assert.deepEqual(unexpectedRequests, []);
});

for (const [segmentationStatus, expectedLabel] of [[null, "not been segmented yet"], ["failed", "Segmentation failed"], ["empty", "No items found"], ["unknown", "Agenda status unknown"]]) {
  test(`empty agenda rows explain ${segmentationStatus ?? "unattempted"} state`, async testContext => {
    const ResultCard = compileResultCard(testContext);
    const { dom, restoreDom } = installDom();
    testContext.mock.method(globalThis, "fetch", async requestUrl => {
      if (String(requestUrl).includes("derived_status")) return jsonResponse({
        agenda_not_generated_yet: segmentationStatus === null,
        agenda_segmentation_status: segmentationStatus,
        agenda_is_empty: segmentationStatus === "empty",
      });
      return jsonResponse({ content: "Synthetic source text", items: [] });
    });
    const container = document.getElementById("root");
    const root = createRoot(container);
    testContext.after(async () => { await act(async () => root.unmount()); restoreDom(); });
    await act(async () => root.render(React.createElement(ResultCard, { hit: { ...TEST_MEETING_HIT, agenda_items: [] } })));
    await act(async () => { container.querySelector('button[title="Expand Document Text"]').click(); await flushAsyncWork(); });
    await act(async () => findButton(container, "Structured Agenda").click());
    assert.ok(container.textContent.includes(expectedLabel));
    if (segmentationStatus !== "empty") assert.doesNotMatch(container.textContent, /No agenda items were found/);
    dom.window.document.body.focus();
  });
}

test("agenda read retry restores saved items without starting segmentation", async testContext => {
  const ResultCard = compileResultCard(testContext);
  const { restoreDom } = installDom();
  const savedAgendaResponse = createDeferred();
  const mutationRequests = [];
  let agendaReadFailed = false;
  testContext.mock.method(globalThis, "fetch", async (requestUrl, requestOptions = {}) => {
    const url = String(requestUrl);
    if (requestOptions.method && requestOptions.method !== "GET") mutationRequests.push(url);
    if (url.includes("derived_status")) return jsonResponse({ agenda_segmentation_status: "completed" });
    if (url.includes("agenda_items")) {
      if (!agendaReadFailed) {
        agendaReadFailed = true;
        return { ok: false, status: 503, statusText: "Service Unavailable", async json() { return {}; } };
      }
      return savedAgendaResponse.promise;
    }
    return jsonResponse({ content: "Synthetic source text" });
  });
  const container = document.getElementById("root");
  const root = createRoot(container);
  testContext.after(async () => { await act(async () => root.unmount()); restoreDom(); });
  await act(async () => root.render(React.createElement(ResultCard, { hit: TEST_MEETING_HIT })));
  await act(async () => { container.querySelector('button[title="Expand Document Text"]').click(); await flushAsyncWork(); });
  await act(async () => { findButton(container, "Structured Agenda").click(); await flushAsyncWork(); });
  assert.match(container.textContent, /Agenda items unavailable/);
  const retryRead = findButton(container, "Retry loading agenda");
  assert.ok(retryRead, "a failed read offers a read-only retry");
  assert.ok(!findButton(container, "Segment Agenda Items"), "a failed read does not offer segmentation");
  await act(async () => { retryRead.click(); await flushAsyncWork(); });
  assert.ok(!findButton(container, "Segment Agenda Items"), "a pending read retry does not offer segmentation");
  assert.equal(findButton(container, "Retry loading agenda")?.disabled, true);
  await act(async () => {
    savedAgendaResponse.resolve(jsonResponse({ items: [{ id: 7, title: "Approve park improvements", description: "Review the park proposal", source: "catalog_agenda_items" }] }));
    await flushAsyncWork();
  });
  assert.match(container.textContent, /Approve park improvements/);
  assert.doesNotMatch(container.textContent, /Agenda items unavailable/);
  assert.deepEqual(mutationRequests, []);
});

test("freshness is not factual verification and cached summary survives refresh failure", async testContext => {
  const ResultCard = compileResultCard(testContext);
  const { restoreDom } = installDom();
  testContext.mock.method(globalThis, "fetch", async requestUrl => {
    if (String(requestUrl).startsWith("/api/summarize/")) return { ok: false, status: 503, json: async () => ({ detail: "provider unavailable" }) };
    if (String(requestUrl).includes("derived_status")) return jsonResponse({ summary_is_stale: false });
    return jsonResponse({ content: "Synthetic source" });
  });
  const container = document.getElementById("root");
  const root = createRoot(container);
  testContext.after(async () => { await act(async () => root.unmount()); restoreDom(); });
  await act(async () => root.render(React.createElement(ResultCard, { hit: { ...TEST_MEETING_HIT, summary: "Saved synthetic summary" } })));
  await act(async () => { container.querySelector('button[title="Expand Document Text"]').click(); await flushAsyncWork(); });
  await act(async () => findButton(container, "AI Summary").click());
  assert.match(container.textContent, /Freshness unknown/);
  assert.doesNotMatch(container.textContent, /Grounded/);
  const regenerate = container.querySelector('button[title^="Regenerate the cached summary"]');
  await act(async () => { regenerate.click(); await flushAsyncWork(); });
  assert.match(container.textContent, /Saved synthetic summary/);
  assert.match(container.textContent, /provider unavailable/);
});

for (const [sourceUrl, emptyAgenda] of [
  ["https://example.org/agenda.pdf", false], ["https://example.org/agenda.html", false],
  ["https://example.org/cancellation.pdf", true],
]) {
  test(`agenda labels and source links stay honest for ${sourceUrl}`, async (testContext) => {
    const ResultCard = compileResultCard(testContext);
    const { dom, restoreDom } = installDom();
    const agendaItems = emptyAgenda ? [] : [{
      title: "Approve the street improvement contract", order: 1,
      page_number: 1, source: "catalog_agenda_items",
    }];
    testContext.mock.method(globalThis, "fetch", async (requestUrl) => {
      const url = String(requestUrl);
      if (url.includes("/derived_status")) return jsonResponse({
        agenda_segmentation_status: emptyAgenda ? "empty" : "complete", agenda_not_generated_yet: false,
        agenda_is_empty: emptyAgenda,
      });
      if (url.includes("/agenda_items")) return jsonResponse({ items: agendaItems });
      if (url.includes("/content")) return jsonResponse({ content: "Street improvement contract" });
      throw new Error(`Unexpected request: ${url}`);
    });
    const container = dom.window.document.getElementById("root");
    const root = createRoot(container);
    testContext.after(async () => {
      await act(async () => root.unmount());
      restoreDom();
    });
    await act(async () => root.render(React.createElement(ResultCard, {
      hit: { ...TEST_MEETING_HIT, url: sourceUrl, agenda_items: agendaItems },
    })));
    await act(async () => {
      container.querySelector('button[title="Expand Document Text"]').click();
      await flushAsyncWork();
    });
    await act(async () => findButton(container, "Structured Agenda").click());

    if (emptyAgenda) {
      assert.equal(container.querySelectorAll("h5").length, 0);
      assert.match(container.textContent, /No agenda items were found in this document\./);
      assert.doesNotMatch(container.textContent, /Not generated yet|The AI was unable/i);
    } else {
      assert.match(container.textContent, /Approve the street improvement contract/);
      assert.match(container.textContent, /Agenda items may be incomplete or inaccurate/);
    }
    assert.doesNotMatch(container.textContent, /Local AI|AI-generated content/i);
    assert.equal(container.querySelector('a[title="Open source document"]').href, sourceUrl);
    assert.equal(container.querySelectorAll('a[href*="#page="]').length, 0);
  });
}

for (const agendaScenario of agendaScenarios) {
  test(agendaScenario.name, { timeout: COMPONENT_INTERACTION_TIMEOUT_MS }, async (testContext) => {
    const ResultCard = compileResultCard(testContext);
    const { dom, restoreDom } = installDom();
    let agendaRefreshes = 0;
    let derivedStatusRefreshes = 0;
    testContext.mock.method(globalThis, "fetch", async (requestUrl) => {
      const url = String(requestUrl);
      if (url.includes("/derived_status")) {
        derivedStatusRefreshes += 1;
        return jsonResponse({});
      }
      if (url.includes("/catalog/42/content")) return jsonResponse({ content: "initial text" });
      if (url.startsWith("/api/segment/42")) return jsonResponse({ task_id: "task-agenda" });
      if (url.includes("/tasks/task-agenda")) {
        return jsonResponse({ status: "complete", result: { items: agendaScenario.taskItems } });
      }
      if (url.includes("/catalog/42/agenda_items")) {
        agendaRefreshes += 1;
        return jsonResponse({ items: agendaScenario.refreshedItems });
      }
      throw new Error(`Unexpected request: ${url}`);
    });

    const container = dom.window.document.getElementById("root");
    const root = createRoot(container);
    testContext.after(async () => {
      await act(async () => root.unmount());
      restoreDom();
    });
    await act(async () => root.render(React.createElement(ResultCard, {
      hit: { ...TEST_MEETING_HIT, agenda_items: [] },
    })));
    await act(async () => {
      container.querySelector('button[title="Expand Document Text"]').click();
      await flushAsyncWork();
    });
    await act(async () => findButton(container, "Structured Agenda").click());
    await act(async () => {
      findButton(container, "Retry Segmentation").click();
      await flushAsyncWork();
      await flushAsyncWork();
    });

    assert.match(container.textContent, new RegExp(agendaScenario.expectedTitle));
    assert.equal(agendaRefreshes, agendaScenario.expectedRefreshes);
    assert.equal(derivedStatusRefreshes, 2);
  });
}
