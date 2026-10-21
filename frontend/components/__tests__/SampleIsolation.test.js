import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import { spawnSync } from "node:child_process";

test("sample API helpers reject unsupported reads and mutation routes locally", () => {
  const execution = spawnSync(process.execPath, ["--input-type=module", "-e", `
    import assert from 'node:assert/strict';
    import {buildApiUrl, buildProtectedCatalogApiUrl} from './lib/api.js';
    assert.equal(buildApiUrl('/search?q=housing'), './demo/search.json');
    assert.equal(buildProtectedCatalogApiUrl('/catalog/706/content'), './demo/catalog_706_content.json');
    for (const path of ['/search/semantic', '/search/unknown', '/tasks/123', '/catalog/706/lineage', '/summarize/706']) {
      assert.throws(() => buildApiUrl(path), /not available in the sample preview/);
      assert.throws(() => buildProtectedCatalogApiUrl(path), /not available in the sample preview/);
    }
  `], { env: { ...process.env, NEXT_PUBLIC_DEMO_MODE: "true" }, encoding: "utf8" });
  assert.equal(execution.status, 0, execution.stderr);
});

test("sample metadata offers every fixture municipality, body and meeting type", () => {
  const { hits } = JSON.parse(fs.readFileSync("public/demo/search.json", "utf8"));
  const metadata = JSON.parse(fs.readFileSync("public/demo/metadata.json", "utf8"));
  assert.deepEqual(metadata.city_options.map(city => city.value).sort(), [...new Set(hits.map(hit => hit.city))].sort());
  assert.deepEqual(metadata.organizations.toSorted(), [...new Set(hits.map(hit => hit.organization))].sort());
  assert.deepEqual(metadata.meeting_types.toSorted(), [...new Set(hits.map(hit => hit.meeting_category))].sort());
  const missing = JSON.parse(fs.readFileSync("public/demo/catalog_706_derived_status.json", "utf8"));
  const stale = JSON.parse(fs.readFileSync("public/demo/catalog_710_derived_status.json", "utf8"));
  assert.equal(missing.summary_not_generated_yet, true);
  assert.equal(stale.summary_is_stale, true);
});

test("sample pagination excludes standalone items until requested", () => {
  const execution = spawnSync(process.execPath, ["--input-type=module", "-e", `
    import assert from 'node:assert/strict';
    import React, {act} from 'react';
    import {createRoot} from 'react-dom/client';
    import {JSDOM} from 'jsdom';
    import {useRecordSearch} from './state/use-record-search.js';
    const dom = new JSDOM('<div id="root"></div>');
    globalThis.window = dom.window;
    globalThis.document = dom.window.document;
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    const hits = Array.from({length:23}, (_, id) => ({id, event_name:'Housing', result_type:'meeting', date:'2026-01-01'}));
    hits.push({id:'item', title:'Housing contract', result_type:'agenda_item', date:'2026-01-01'});
    globalThis.fetch = async url => {
      assert.equal(url, './demo/search.json');
      return {ok:true,json:async()=>({hits})};
    };
    let search;
    function Probe({includeAgendaItems=false}) {
      search = useRecordSearch({query:'',cityFilter:'',orgFilter:'',meetingTypeFilter:'',searchMode:'keyword',sortMode:'newest',includeAgendaItems});
      return React.createElement('p', null, search.status);
    }
    const root = createRoot(document.getElementById('root'));
    const settle = async () => act(async()=>{await new Promise(resolve=>setTimeout(resolve,450));});
    await act(async()=>root.render(React.createElement(Probe)));
    await settle();
    assert.equal(search.results.length,20);
    assert.equal(search.totalHits,23);
    await act(async()=>{search.loadMore();search.loadMore();});
    assert.equal(search.results.length,23);
    assert.equal(new Set(search.results.map(hit=>hit.id)).size,23);
    await act(async()=>root.render(React.createElement(Probe,{includeAgendaItems:true})));
    await settle();
    await act(async()=>search.loadMore());
    assert.equal(search.results.length,24);
    assert.equal(search.results.some(hit=>hit.id==='item'),true);
    await act(async()=>root.unmount());
    dom.window.close();
  `], { env: { ...process.env, NEXT_PUBLIC_DEMO_MODE: "true" }, encoding: "utf8" });
  assert.equal(execution.status, 0, execution.stderr);
});
