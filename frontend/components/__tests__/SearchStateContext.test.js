import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const statePath = path.resolve(process.cwd(), "state/search-state.js");
const pagePath = path.resolve(process.cwd(), "app/page.js");
const hubPath = path.resolve(process.cwd(), "components/SearchHub.js");

const stateSource = fs.readFileSync(statePath, "utf8");
const pageSource = fs.readFileSync(pagePath, "utf8");
const hubSource = fs.readFileSync(hubPath, "utf8");

test("defines SearchStateProvider and useSearchState hook", () => {
  assert.match(stateSource, /export function SearchStateProvider/);
  assert.match(stateSource, /export function useSearchState/);
  assert.match(stateSource, /query, setQuery/);
  assert.match(stateSource, /includeAgendaItems, setIncludeAgendaItems/);
});

test("wraps HomeContent in SearchStateProvider", () => {
  assert.match(pageSource, /<SearchStateProvider>/);
  assert.match(pageSource, /<HomeContent \/>/);
});

test("SearchHub consumes shared state context", () => {
  assert.match(hubSource, /import \{ useSearchState \} from \"\.\.\/state\/search-state\";/);
  assert.match(hubSource, /const \{\s*query, setQuery,/);
});
