"use client";

import { useState, useEffect, useCallback } from "react";
import { Database, Github, Info, Loader2, Search as SearchIcon } from "lucide-react";

import SearchHub from "../components/SearchHub";
import ResultCard from "../components/ResultCard";
import PersonProfile from "../components/PersonProfile";
import { TooltipProvider } from "@/components/ui/tooltip";
import { buildApiUrl, getApiHeaders, isDemoMode } from "../lib/api";

export default function Home() {
  // Search State
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [totalHits, setTotalHits] = useState(0); 
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  
  // Filter State
  const [cityFilter, setCityFilter] = useState("");
  const [meetingTypeFilter, setMeetingTypeFilter] = useState("");
  const [orgFilter, setOrgFilter] = useState("");
  const [includeAgendaItems, setIncludeAgendaItems] = useState(false);
  const [sortMode, setSortMode] = useState("newest"); // newest | oldest | relevance
  
  // Metadata State
  const [availableCities, setAvailableCities] = useState([]);
  const [availableOrgs, setAvailableOrgs] = useState([]);

  // Person Profile Modal State
  const [selectedPersonId, setSelectedPersonId] = useState(null);
  const demoMode = isDemoMode();

  /**
   * The heart of the search UI.
   * It talks to our FastAPI backend and handles both new searches 
   * and "Load More" requests.
   */
  const performSearch = useCallback(async (isLoadMore = false) => {
    // In static demo mode, show all fixture records when the query is empty.
    // In live API mode, keep the existing behavior that requires a query string.
    if (!query.trim() && !demoMode) {
      if (!isLoadMore) {
        setResults([]);
        setTotalHits(0);
      }
      setSearchError("");
      return;
    }
    
    setLoading(true);
    if (!isLoadMore) setIsSearching(true);

    try {
      setSearchError("");
      const currentOffset = isLoadMore ? offset + 20 : 0;

      if (demoMode) {
        const res = await fetch(buildApiUrl("/search"));
        if (!res.ok) {
          let detail = res.statusText || "Unknown error";
          try {
            const payload = await res.json();
            detail = payload?.detail || detail;
          } catch (e) {
            // ignore JSON parsing errors in demo mode
          }
          setSearchError(`Search failed (${res.status}): ${detail}`);
          return;
        }
        const data = await res.json();
        const allHits = data.hits || [];
        const normalizedQuery = query.trim().toLowerCase();
        const normalizedCity = (cityFilter || "").toLowerCase();
        const normalizedOrg = (orgFilter || "").toLowerCase();
        const normalizedMeetingType = (meetingTypeFilter || "").toLowerCase();

        const filteredHits = allHits.filter((hit) => {
          if (!includeAgendaItems && hit.result_type === "agenda_item") return false;
          const haystack = [
            hit.event_name,
            hit.title,
            hit.content,
            hit.summary,
            ...(hit.topics || []),
          ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();

          if (normalizedQuery && !haystack.includes(normalizedQuery)) return false;
          if (normalizedCity && normalizedCity !== "all" && (hit.city || "").toLowerCase() !== normalizedCity) return false;
          if (
            normalizedMeetingType &&
            normalizedMeetingType !== "all" &&
            (hit.meeting_category || "").toLowerCase() !== normalizedMeetingType
          ) {
            return false;
          }
          if (normalizedOrg && normalizedOrg !== "all" && (hit.organization || "").toLowerCase() !== normalizedOrg) return false;
          return true;
        });

        const sortedHits = (() => {
          if (sortMode === "relevance") return filteredHits;
          const dir = sortMode === "oldest" ? 1 : -1;
          const parseDate = (value) => {
            const s = (value || "").toString().trim();
            const t = Date.parse(s);
            return Number.isFinite(t) ? t : 0;
          };
          return [...filteredHits].sort((a, b) => dir * (parseDate(a.date) - parseDate(b.date)));
        })();

        const pagedHits = sortedHits.slice(currentOffset, currentOffset + 20);
        setResults((prev) => (isLoadMore ? [...prev, ...pagedHits] : pagedHits));
        setTotalHits(sortedHits.length);
        setOffset(currentOffset);
        setHasMore(currentOffset + 20 < sortedHits.length);
        return;
      }
      
      // Build the URL with our search query and any active filters
      let url = buildApiUrl(`/search?q=${encodeURIComponent(query)}&limit=20&offset=${currentOffset}`);
      
      if (cityFilter && cityFilter !== "all") url += `&city=${encodeURIComponent(cityFilter)}`;
      if (includeAgendaItems) url += `&include_agenda_items=true`;
      url += `&sort=${encodeURIComponent(sortMode)}`;
      if (meetingTypeFilter && meetingTypeFilter !== "all") url += `&meeting_type=${encodeURIComponent(meetingTypeFilter)}`;
      if (orgFilter && orgFilter !== "all") url += `&org=${encodeURIComponent(orgFilter)}`;

      const res = await fetch(url, {
        headers: getApiHeaders({ useAuth: true })
      });
      if (!res.ok) {
        let detail = res.statusText || "Unknown error";
        try {
          const payload = await res.json();
          detail = payload?.detail || detail;
        } catch (e) {
          // ignore JSON parsing errors
        }
        setSearchError(`Search failed (${res.status}): ${detail}`);
        return;
      }

      const data = await res.json();
      
      const newHits = data.hits || [];
      
      // Update results: append if loading more, otherwise replace
      setResults(prev => isLoadMore ? [...prev, ...newHits] : newHits);
      setTotalHits(data.estimatedTotalHits || 0);
      setOffset(currentOffset);
      setHasMore(newHits.length === 20); 
    } catch (error) {
      console.error("Search failed:", error);
      setSearchError("Search failed: network error");
    } finally {
      setLoading(false);
      setIsSearching(false);
    }
  }, [query, cityFilter, includeAgendaItems, sortMode, meetingTypeFilter, orgFilter, offset, demoMode]);

  // Debouncing: Prevents searching on EVERY single keypress (waits 400ms)
  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      setOffset(0);
      performSearch(false);
    }, 400);

    return () => clearTimeout(delayDebounceFn);
  }, [query, cityFilter, includeAgendaItems, sortMode, meetingTypeFilter, orgFilter]);

  // Initial Load: Fetch valid filter options from the search engine
  useEffect(() => {
    fetch(buildApiUrl("/metadata"), {
      headers: getApiHeaders({ useAuth: true })
    })
      .then(res => res.json())
      .then(data => {
        setAvailableCities(data.cities || []);
        setAvailableOrgs(data.organizations || []);
      })
      .catch(err => console.error("Metadata fetch failed", err));
  }, []);

  // Function to reset the application to its initial state
  const resetApp = () => {
    setQuery("");
    setResults([]);
    setCityFilter("");
    setMeetingTypeFilter("");
    setOrgFilter("");
    setIncludeAgendaItems(false);
    setSortMode("newest");
    setOffset(0);
    setHasMore(false);
    setSearchError("");
  };

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-gray-50/50 flex flex-col font-sans antialiased">
        {/* Navbar / Header */}
        <header className="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center gap-8">
              <div className="flex items-center gap-2 cursor-pointer group" onClick={resetApp}>
                <div className="bg-blue-600 p-1.5 rounded-lg shadow-sm group-hover:bg-blue-700 transition-colors">
                  <Database className="w-5 h-5 text-white" />
                </div>
                <h1 className="text-lg font-bold text-gray-900 tracking-tight">
                  Town Council <span className="text-blue-600 font-medium">Insight</span>
                </h1>
              </div>
              
              <nav className="hidden md:flex items-center gap-6">
                <button onClick={resetApp} className="text-sm font-semibold text-blue-600 border-b-2 border-blue-600 pb-1">Search</button>
                <a href="https://github.com/manumissio/town-council" target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-gray-500 hover:text-blue-600 transition-colors flex items-center gap-1.5">
                  <Github className="w-4 h-4" /> GitHub
                </a>
              </nav>
            </div>
            {demoMode && (
              <span className="text-[10px] font-black uppercase tracking-widest bg-amber-100 text-amber-800 px-3 py-1.5 rounded-full border border-amber-200">
                Demo Mode (Static)
              </span>
            )}
          </div>
        </header>

        <main className="flex-1">
          {/* Hero / Search Unit */}
          <SearchHub 
            query={query} setQuery={setQuery}
            cityFilter={cityFilter} setCityFilter={setCityFilter}
            orgFilter={orgFilter} setOrgFilter={setOrgFilter}
            meetingTypeFilter={meetingTypeFilter} setMeetingTypeFilter={setMeetingTypeFilter}
            includeAgendaItems={includeAgendaItems} setIncludeAgendaItems={setIncludeAgendaItems}
            sortMode={sortMode} setSortMode={setSortMode}
            availableCities={availableCities} availableOrgs={availableOrgs}
            isSearching={isSearching} resetApp={resetApp}
          />
          {searchError && (
            <div className="max-w-6xl mx-auto px-4 mt-4">
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                {searchError}
              </div>
            </div>
          )}

          <div className="max-w-5xl mx-auto px-4 py-12">
            <div className="space-y-8">
              
              {/* Results Metadata Bar */}
              {query && !loading && (
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 text-sm font-bold text-gray-400 uppercase tracking-widest">
                    <Database className="w-4 h-4" /> Found {totalHits} relevant records
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
                    onPersonClick={(id) => setSelectedPersonId(id)}
                    onTopicClick={(topic) => setQuery(topic)}
                  />
                ))}

                {/* Empty State / 0 Results */}
                {query && !loading && results.length === 0 && (
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
                      onClick={() => performSearch(true)}
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

        {/* Overlays */}
        <PersonProfile 
          personId={selectedPersonId} 
          onClose={() => setSelectedPersonId(null)} 
        />
      </div>
    </TooltipProvider>
  );
}
