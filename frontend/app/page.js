"use client";

import { useState, useEffect, useRef } from "react";
import { Database, Github, Info, Loader2 } from "lucide-react";

import SearchHub from "../components/SearchHub";
import ResultCard from "../components/ResultCard";
import { TooltipProvider } from "@/components/ui/tooltip";
import { buildApiUrl, getApiHeaders, isDemoMode, readJsonResponse } from "../lib/api";
import { useRecordSearch } from "../state/use-record-search";
import { SearchStateProvider, useSearchState } from "../state/search-state";

function HomeContent() {
  const {
    query,
    setQuery,
    cityFilter,
    setCityFilter,
    meetingTypeFilter,
    setMeetingTypeFilter,
    orgFilter,
    setOrgFilter,
    includeAgendaItems,
    setIncludeAgendaItems,
    searchMode,
    setSearchMode,
    sortMode,
    setSortMode,
  } = useSearchState();
  const demoMode = isDemoMode();
  const { results, totalHits, hasMore, status, error: searchError, retry, loadMore: handleLoadMore } = useRecordSearch({
    query, cityFilter, orgFilter, meetingTypeFilter, includeAgendaItems, searchMode,
    sortMode: !query.trim() && sortMode === "relevance" ? "newest" : sortMode,
  });
  const loading = status === "loading";
  const isSearching = loading;
  const [availableCities, setAvailableCities] = useState([]);
  const [availableOrgs, setAvailableOrgs] = useState([]);
  const [meetingTypes, setMeetingTypes] = useState([]);
  const [metadataError, setMetadataError] = useState("");
  const [metadataVersion, setMetadataVersion] = useState(0);
  const [semanticEnabled, setSemanticEnabled] = useState(false);
  const [capabilityError, setCapabilityError] = useState("");
  const [selectedRecord, setSelectedRecord] = useState(null);
  const selectedRecordRef = useRef(null);

  useEffect(() => {
    if (selectedRecord) selectedRecordRef.current?.focus();
  }, [selectedRecord]);

  const openRelatedMeeting = (related) => {
    setSelectedRecord({
      ...related,
      catalog_id: related.id,
      event_name: related.title,
    });
  };

  const searchTopic = (topic) => {
    setSelectedRecord(null);
    setQuery(topic);
  };

  useEffect(() => {
    const controller = new AbortController();
    setMetadataError("");
    fetch(buildApiUrl("/metadata"), { headers: getApiHeaders(), signal: controller.signal })
      .then(response => readJsonResponse(response, "Load filters"))
      .then(metadata => {
        if (controller.signal.aborted) return;
        setAvailableCities(metadata.city_options || (metadata.cities || []).map(city => ({ value: city, label: city })));
        setAvailableOrgs(metadata.organizations || []);
        setMeetingTypes(metadata.meeting_types || []);
      })
      .catch(error => { if (!controller.signal.aborted) setMetadataError(error.message); });
    if (!demoMode) {
      setCapabilityError("");
      fetch(buildApiUrl("/search/capabilities"), { signal: controller.signal })
        .then(response => readJsonResponse(response, "Load search capabilities"))
        .then(capabilities => { if (!controller.signal.aborted) setSemanticEnabled(capabilities.semantic_enabled === true); })
        .catch(error => { if (!controller.signal.aborted) { setSemanticEnabled(false); setCapabilityError(error.message); } });
    }
    return () => controller.abort();
  }, [metadataVersion, demoMode]);

  const resetApp = () => {
    setSelectedRecord(null);
    setQuery("");
    setCityFilter("");
    setMeetingTypeFilter("");
    setOrgFilter("");
    setIncludeAgendaItems(false);
    setSearchMode("keyword");
    setSortMode("newest");
    retry();
  };

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-gray-50/50 flex flex-col font-sans antialiased">
        {/* Navbar / Header */}
        <header className="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center gap-8">
              <button className="flex items-center gap-2 cursor-pointer group" onClick={resetApp} aria-label="Return to recent meetings">
                <div className="bg-blue-600 p-1.5 rounded-lg shadow-sm group-hover:bg-blue-700 transition-colors">
                  <Database className="w-5 h-5 text-white" />
                </div>
                <h1 className="text-lg font-bold text-gray-900 tracking-tight">
                  Town Council <span className="text-blue-600 font-medium">Insight</span>
                </h1>
              </button>
              
              <nav className="hidden md:flex items-center gap-6">
                <button onClick={resetApp} className="text-sm font-semibold text-blue-600 border-b-2 border-blue-600 pb-1">Search</button>
                <a href="https://github.com/manumissio/town-council" target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-gray-500 hover:text-blue-600 transition-colors flex items-center gap-1.5">
                  <Github className="w-4 h-4" /> GitHub
                </a>
              </nav>
            </div>
            {demoMode && (
              <span className="text-[10px] font-black uppercase tracking-widest bg-amber-100 text-amber-800 px-3 py-1.5 rounded-full border border-amber-200">
                Synthetic sample · Read-only
              </span>
            )}
          </div>
        </header>

        <main className="flex-1">
          {selectedRecord ? (
            <section ref={selectedRecordRef} tabIndex={-1} aria-label="Related meeting" className="max-w-5xl mx-auto px-4 py-12 space-y-6">
              <button className="text-sm font-semibold text-blue-600 underline" onClick={() => setSelectedRecord(null)}>Back to search results</button>
              <ResultCard
                key={selectedRecord.catalog_id}
                hit={selectedRecord}
                initiallyExpanded
                onTopicClick={searchTopic}
                onRelatedMeetingClick={openRelatedMeeting}
              />
            </section>
          ) : <>
          {/* Hero / Search Unit */}
          <SearchHub 
            availableCities={availableCities} availableOrgs={availableOrgs}
            meetingTypes={meetingTypes} semanticEnabled={semanticEnabled}
            isSearching={isSearching} resetApp={resetApp}
          />
          {(metadataError || capabilityError) && <div role="alert" className="max-w-6xl mx-auto px-4 mt-4">
            <p>{metadataError || capabilityError}</p>
            <button className="underline" onClick={() => setMetadataVersion(version => version + 1)}>Retry filters and capabilities</button>
          </div>}
          <p className="max-w-6xl mx-auto px-4 mt-4 text-sm text-gray-600">
            {demoMode ? "Synthetic, read-only sample. Keyword matching only; this preview does not simulate semantic ranking." : semanticEnabled ? "Semantic search is configured. Keyword mode browses local records." : "Semantic search is unavailable or disabled. Keyword search remains available."}
            {!query.trim() && " Browse by date; relevance needs a search query."}
          </p>
          {demoMode && <p className="max-w-6xl mx-auto px-4 mt-2 text-sm text-amber-800">These are invented examples, not evidence of extraction accuracy. <a className="underline" href="https://github.com/manumissio/town-council/blob/master/docs/OPERATIONS.md#local-demo-preview">Return to local records with a separate live build.</a></p>}
          {/* Product decision (temporary):
             We are pausing Topic Momentum/Civic Signals to reduce first-screen ambiguity.
             Keep the initial interaction focused on search input and result cards. */}
          {searchError && (
            <div className="max-w-6xl mx-auto px-4 mt-4">
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                <p role="alert">{searchError}</p>
                <button onClick={retry} className="underline font-bold mt-2">Retry search</button>
                {" · "}<a className="underline" href="https://github.com/manumissio/town-council/blob/master/docs/OPERATIONS.md#1-start-stack">Setup help</a>
              </div>
            </div>
          )}

          <div className="max-w-5xl mx-auto px-4 py-12">
            <div className="space-y-8">
              
              {/* Results Metadata Bar */}
              {status === "ready" && (
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 text-sm font-bold text-gray-400 uppercase tracking-widest">
                    <Database className="w-4 h-4" /> {demoMode ? "Sample records:" : "Estimated matching records:"} {totalHits}
                  </div>
                  <div className="flex gap-2">
                    {cityFilter && cityFilter !== "all" && <span className="text-[10px] font-bold bg-blue-50 text-blue-600 px-2 py-1 rounded uppercase">{cityFilter}</span>}
                    {orgFilter && orgFilter !== "all" && <span className="text-[10px] font-bold bg-purple-50 text-purple-600 px-2 py-1 rounded uppercase">{orgFilter}</span>}
                    {meetingTypeFilter && meetingTypeFilter !== "all" && <span className="text-[10px] font-bold bg-gray-100 text-gray-600 px-2 py-1 rounded uppercase">{meetingTypeFilter}</span>}
                  </div>
                </div>
              )}

              {/* Results Stream */}
              <div className="space-y-8">
                {results.map((hit) => (
                  <ResultCard 
                    key={hit.id} 
                    hit={hit} 
                    onTopicClick={searchTopic}
                    onRelatedMeetingClick={openRelatedMeeting}
                  />
                ))}

                {/* Empty State / 0 Results */}
                {loading && <p role="status">{results.length ? "Loading more records…" : "Connecting to meeting records…"}</p>}
                {status === "query-required" && <p role="status">Enter a query to use semantic search.</p>}
                {status === "empty" && <div role="status" className="rounded-xl border bg-white p-8 space-y-3">
                  <h2 className="text-xl font-bold">No records indexed yet</h2>
                  <p>Starting the app does not collect meeting records. Ingest and index records to browse them here.</p>
                  <a className="underline" href="https://github.com/manumissio/town-council/blob/master/README.md#quickstart">Read the setup and ingestion steps</a>
                  <p>Prefer a walkthrough? Use the separate <a className="underline" href="https://github.com/manumissio/town-council/blob/master/docs/OPERATIONS.md#local-demo-preview">synthetic sample preview</a>.</p>
                </div>}
                {status === "no-matches" && (
                  <div className="text-center py-24 bg-white border border-gray-100 rounded-[3rem] shadow-sm">
                    <div className="max-w-sm mx-auto space-y-6">
                      <div className="text-5xl bg-gray-50 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4">🔍</div>
                      <div>
                        <h3 className="text-xl font-bold text-gray-900">No matches found</h3>
                        <p className="text-gray-500 leading-relaxed mt-2 text-sm px-4">
                          We couldn't find any documents matching "{query}" with the current filters.
                        </p>
                      </div>
                      <button onClick={resetApp} className="px-8 py-3 bg-blue-600 text-white font-bold rounded-2xl hover:bg-blue-700 transition-all shadow-lg active:scale-95">
                        Clear all filters
                      </button>
                    </div>
                  </div>
                )}

                {/* Pagination Controls */}
                {hasMore && (
                  <div className="pt-8 text-center">
                    <button 
                      onClick={handleLoadMore}
                      disabled={loading}
                      className="inline-flex items-center gap-2 px-12 py-4 bg-white border border-gray-200 text-gray-700 text-sm font-bold rounded-full hover:bg-gray-50 transition-all shadow-sm disabled:opacity-50"
                    >
                      {loading ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Loading...
                        </>
                      ) : "Load More Records"}
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
          </>}
        </main>

        <footer className="bg-white border-t border-gray-200 py-12 mt-12">
          <div className="max-w-5xl mx-auto px-4 text-center space-y-4">
            <p className="text-[11px] text-gray-400 font-bold tracking-widest uppercase">Town Council Insight</p>
            <p className="text-sm text-gray-500 max-w-xl mx-auto leading-relaxed">
              An open-source initiative originally launched in 2017 by Data for Democracy to improve civic transparency.
            </p>
            <div className="flex items-center justify-center gap-4 pt-4">
              <a href="https://open-civic-data.readthedocs.io/en/latest/index.html" target="_blank" rel="noopener noreferrer" className="text-[11px] font-bold text-gray-400 hover:text-blue-600 transition-colors uppercase tracking-widest flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5" /> OCD Standards
              </a>
            </div>
          </div>
        </footer>

      </div>
    </TooltipProvider>
  );
}

export default function Home() {
  // Shared search/filter state is intentionally centralized here so future
  // multi-panel views (when Signals resumes) stay synchronized.
  return (
    <SearchStateProvider>
      <HomeContent />
    </SearchStateProvider>
  );
}
