import { useEffect, useRef, useState } from "react";
import { buildApiUrl, getApiHeaders, isDemoMode, readJsonResponse } from "../lib/api.js";

const PAGE_SIZE = 20;
const SEARCH_DELAY_MS = 400;

function samplePage(hits, criteria, offset) {
  const { query, cityFilter, orgFilter, meetingTypeFilter, includeAgendaItems, sortMode } = criteria;
  const filtered = hits.filter(hit => {
    if (!includeAgendaItems && hit.result_type === "agenda_item") return false;
    if (cityFilter && hit.city?.toLowerCase() !== cityFilter.toLowerCase()) return false;
    if (orgFilter && hit.organization !== orgFilter) return false;
    if (meetingTypeFilter && hit.meeting_category !== meetingTypeFilter) return false;
    const text = [hit.event_name, hit.title, hit.content, hit.summary, ...(hit.topics || [])].join(" ").toLowerCase();
    return text.includes(query.trim().toLowerCase());
  });
  if (sortMode !== "relevance") {
    const direction = sortMode === "oldest" ? 1 : -1;
    filtered.sort((left, right) => direction * ((Date.parse(left.date) || 0) - (Date.parse(right.date) || 0)));
  }
  return { hits: filtered.slice(offset, offset + PAGE_SIZE), estimatedTotalHits: filtered.length };
}

async function readSearchPage(criteria, offset, signal) {
  const { query, cityFilter, orgFilter, meetingTypeFilter, includeAgendaItems, searchMode, sortMode } = criteria;
  const semanticMode = searchMode === "semantic";
  const basePath = semanticMode ? "/search/semantic" : "/search";
  let url = `${basePath}?q=${encodeURIComponent(query.trim())}&limit=20&offset=${offset}`;
  if (!semanticMode) url += `&sort=${encodeURIComponent(sortMode)}`;
  if (cityFilter) url += `&city=${encodeURIComponent(cityFilter)}`;
  if (orgFilter) url += `&org=${encodeURIComponent(orgFilter)}`;
  if (meetingTypeFilter) url += `&meeting_type=${encodeURIComponent(meetingTypeFilter)}`;
  if (includeAgendaItems) url += "&include_agenda_items=true";
  const payload = await readJsonResponse(await fetch(buildApiUrl(url), { signal, headers: getApiHeaders() }), "Search");
  if (!Array.isArray(payload.hits)) throw new Error("Search returned an unreadable response.");
  return isDemoMode() ? samplePage(payload.hits, criteria, offset) : payload;
}

const INITIAL_SEARCH = { results: [], totalHits: 0, offset: 0, hasMore: false, status: "loading", error: "" };

export function useRecordSearch(criteria) {
  const [search, setSearch] = useState(INITIAL_SEARCH);
  const [retryVersion, setRetryVersion] = useState(0);
  const activeSearch = useRef(null);
  const identity = JSON.stringify(criteria);

  useEffect(() => {
    const controller = new AbortController();
    const request = { controller, busy: false, criteria: JSON.parse(identity), offset: 0 };
    activeSearch.current = request;
    setSearch(INITIAL_SEARCH);
    const timer = setTimeout(() => void loadPage(request, false), SEARCH_DELAY_MS);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [identity, retryVersion]);

  async function loadPage(request, append) {
    if (!request || request.busy || request.controller.signal.aborted) return;
    if (request.criteria.searchMode === "semantic" && !request.criteria.query.trim()) {
      setSearch({ ...INITIAL_SEARCH, status: "query-required" });
      return;
    }
    request.busy = true;
    setSearch(previous => ({ ...previous, status: "loading", error: "" }));
    const offset = append ? request.offset + PAGE_SIZE : 0;
    try {
      const page = await readSearchPage(request.criteria, offset, request.controller.signal);
      if (request.controller.signal.aborted) return;
      request.offset = offset;
      const unfiltered = !request.criteria.query.trim() && !request.criteria.cityFilter && !request.criteria.orgFilter && !request.criteria.meetingTypeFilter;
      // A meeting-only zero cannot prove that standalone indexed items do not exist.
      let emptyCorpus = false;
      if (unfiltered && !append && page.hits.length === 0 && page.estimatedTotalHits === 0) {
        const corpus = await readSearchPage({ ...request.criteria, includeAgendaItems: true }, 0, request.controller.signal);
        emptyCorpus = corpus.hits.length === 0 && corpus.estimatedTotalHits === 0;
      }
      if (request.controller.signal.aborted) return;
      setSearch(previous => ({
        results: append ? [...previous.results, ...page.hits] : page.hits,
        totalHits: page.estimatedTotalHits ?? page.totalHits ?? page.hits.length,
        offset,
        hasMore: isDemoMode() ? offset + PAGE_SIZE < page.estimatedTotalHits : page.hits.length === PAGE_SIZE,
        status: page.hits.length || append ? "ready" : emptyCorpus ? "empty" : "no-matches",
        error: "",
      }));
    } catch (error) {
      if (request.controller.signal.aborted) return;
      setSearch(previous => ({ ...previous, status: "error", error: `Search failed: ${error.message}` }));
    } finally {
      request.busy = false;
    }
  }

  return {
    ...search,
    retry: () => setRetryVersion(version => version + 1),
    loadMore: () => void loadPage(activeSearch.current, true),
  };
}
