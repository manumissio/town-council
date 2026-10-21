import assert from "node:assert/strict";
import test from "node:test";
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";
import { useRecordSearch } from "../../state/use-record-search.js";

const criteria = { query: "", cityFilter: "", orgFilter: "", meetingTypeFilter: "", includeAgendaItems: false, searchMode: "keyword", sortMode: "newest" };
const response = (hits, total = hits.length) => ({ ok: true, json: async () => ({ hits, estimatedTotalHits: total }) });

async function mountSearch(testContext, initialCriteria = criteria) {
  const dom = new JSDOM("<div id='root'></div>");
  const previousWindow = globalThis.window;
  const previousDocument = globalThis.document;
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  const root = createRoot(document.getElementById("root"));
  let search;
  function Probe({ filters }) {
    search = useRecordSearch(filters);
    return React.createElement("p", null, search.status);
  }
  const render = async (filters) => act(async () => root.render(React.createElement(Probe, { filters })));
  await render(initialCriteria);
  testContext.after(async () => {
    await act(async () => root.unmount());
    dom.window.close();
    globalThis.window = previousWindow;
    globalThis.document = previousDocument;
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  });
  return { current: () => search, render };
}

const settle = async () => act(async () => { await new Promise(resolve => setTimeout(resolve, 450)); });

test("first load browses recent meetings and distinguishes an empty index", async t => {
  const requests = [];
  t.mock.method(globalThis, "fetch", async url => { requests.push(url); return response([]); });
  const search = await mountSearch(t);
  assert.equal(search.current().status, "loading");
  await settle();
  assert.equal(search.current().status, "empty");
  assert.match(requests[0], /q=&limit=20&offset=0.*sort=newest/);
});

test("filtered emptiness is no matches, and failed reads are unavailable", async t => {
  t.mock.method(globalThis, "fetch", async () => response([]));
  const search = await mountSearch(t, { ...criteria, cityFilter: "ca_berkeley" });
  await settle();
  assert.equal(search.current().status, "no-matches");
  t.mock.method(globalThis, "fetch", async () => { throw new TypeError("offline"); });
  await act(async () => search.current().retry());
  await settle();
  assert.equal(search.current().status, "error");
  assert.match(search.current().error, /offline/);
});

test("semantic blank query asks for text without sending a request", async t => {
  t.mock.method(globalThis, "fetch", async () => { throw new Error("must not request"); });
  const search = await mountSearch(t, { ...criteria, searchMode: "semantic" });
  await settle();
  assert.equal(search.current().status, "query-required");
});

test("only the active search owns late results, including its page loads", async t => {
  let finishOld;
  t.mock.method(globalThis, "fetch", async url => {
    if (url.includes("q=old")) return new Promise(resolve => { finishOld = resolve; });
    return response([{ id: "new" }]);
  });
  const search = await mountSearch(t, { ...criteria, query: "old" });
  await settle();
  await search.render({ ...criteria, query: "new" });
  await settle();
  await act(async () => finishOld(response([{ id: "old" }])));
  assert.deepEqual(search.current().results, [{ id: "new" }]);
});

test("repeated load-more requests append a page once and filters reset it", async t => {
  const firstPage = Array.from({ length: 20 }, (_, id) => ({ id }));
  let finishPage;
  t.mock.method(globalThis, "fetch", async url => url.includes("offset=20")
    ? new Promise(resolve => { finishPage = resolve; }) : response(firstPage, 21));
  const search = await mountSearch(t);
  await settle();
  await act(async () => { search.current().loadMore(); search.current().loadMore(); });
  await act(async () => finishPage(response([{ id: 20 }], 21)));
  assert.equal(search.current().results.length, 21);
  assert.equal(new Set(search.current().results.map(hit => hit.id)).size, 21);
  await search.render({ ...criteria, cityFilter: "ca_berkeley" });
  assert.deepEqual(search.current().results, []);
  await settle();
  assert.equal(search.current().offset, 0);
});

test("a corpus containing only standalone agenda items is not called empty", async t => {
  t.mock.method(globalThis, "fetch", async url => url.includes("include_agenda_items=true") ? response([{ id: "item" }]) : response([]));
  const search = await mountSearch(t);
  await settle();
  assert.equal(search.current().status, "no-matches");
});

test("configured semantic errors remain errors without keyword substitution", async t => {
  const paths = [];
  t.mock.method(globalThis, "fetch", async url => {
    paths.push(url);
    return { ok: false, status: 503, json: async () => ({ detail: "semantic service unavailable" }) };
  });
  const search = await mountSearch(t, { ...criteria, searchMode: "semantic", query: "housing" });
  await settle();
  assert.equal(search.current().status, "error");
  assert.match(search.current().error, /semantic service unavailable/);
  assert.equal(paths.every(url => url.includes("/search/semantic?")), true);
});
