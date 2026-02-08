"use client";

import { useState, useEffect, useCallback } from "react";
import { Database, Github, Info, Loader2, Search as SearchIcon } from "lucide-react";

import SearchHub from "../components/SearchHub";
import ResultCard from "../components/ResultCard";
import PersonProfile from "../components/PersonProfile";
import { TooltipProvider } from "@/components/ui/tooltip";
import { API_BASE_URL, getApiHeaders } from "../lib/api";

export default function Home() {
  // Search State
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [totalHits, setTotalHits] = useState(0); 
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  
  // Filter State
  const [cityFilter, setCityFilter] = useState("");
  const [meetingTypeFilter, setMeetingTypeFilter] = useState("");
  const [orgFilter, setOrgFilter] = useState("");
  
  // Metadata State
  const [availableCities, setAvailableCities] = useState([]);
  const [availableOrgs, setAvailableOrgs] = useState([]);

  // Person Profile Modal State
  const [selectedPersonId, setSelectedPersonId] = useState(null);

  /**
   * The heart of the search UI.
   * It talks to our FastAPI backend and handles both new searches 
   * and "Load More" requests.
   */
  const performSearch = useCallback(async (isLoadMore = false) => {
    if (!query.trim()) {
      if (!isLoadMore) {
        setResults([]);
        setTotalHits(0);
      }
      return;
    }
    
    setLoading(true);
    if (!isLoadMore) setIsSearching(true);

    try {
      const currentOffset = isLoadMore ? offset + 20 : 0;
      
      // Build the URL with our search query and any active filters
      let url = `${API_BASE_URL}/search?q=${encodeURIComponent(query)}&limit=20&offset=${currentOffset}`;
      
      if (cityFilter && cityFilter !== "all") url += `&city=${encodeURIComponent(cityFilter)}`;
      if (meetingTypeFilter && meetingTypeFilter !== "all") url += `&meeting_type=${encodeURIComponent(meetingTypeFilter)}`;
      if (orgFilter && orgFilter !== "all") url += `&org=${encodeURIComponent(orgFilter)}`;

      const res = await fetch(url, {
        headers: getApiHeaders({ useAuth: true })
      });
      const data = await res.json();
      
      const newHits = data.hits || [];
      
      // Update results: append if loading more, otherwise replace
      setResults(prev => isLoadMore ? [...prev, ...newHits] : newHits);
      setTotalHits(data.estimatedTotalHits || 0);
      setOffset(currentOffset);
      setHasMore(newHits.length === 20); 
    } catch (error) {
      console.error("Search failed:", error);
    } finally {
      setLoading(false);
      setIsSearching(false);
    }
  }, [query, cityFilter, meetingTypeFilter, orgFilter, offset]);

  // Debouncing: Prevents searching on EVERY single keypress (waits 400ms)
  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      setOffset(0);
      performSearch(false);
    }, 400);

    return () => clearTimeout(delayDebounceFn);
  }, [query, cityFilter, meetingTypeFilter, orgFilter]);

  // Initial Load: Fetch valid filter options from the search engine
  useEffect(() => {
    fetch(`${API_BASE_URL}/metadata`, {
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
    setOffset(0);
    setHasMore(false);
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
          </div>
        </header>

        <main className="flex-1">
          {/* Hero / Search Unit */}
          <SearchHub 
            query={query} setQuery={setQuery}
            cityFilter={cityFilter} setCityFilter={setCityFilter}
            orgFilter={orgFilter} setOrgFilter={setOrgFilter}
            meetingTypeFilter={meetingTypeFilter} setMeetingTypeFilter={setMeetingTypeFilter}
            availableCities={availableCities} availableOrgs={availableOrgs}
            isSearching={isSearching} resetApp={resetApp}
          />

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
