"use client";

import { useState, useEffect, useCallback } from "react";
import DOMPurify from "isomorphic-dompurify";
import { 
  Search, FileText, Calendar, MapPin, Sparkles, Building2, 
  Table as TableIcon, ChevronDown, ChevronUp, Filter, 
  X, ExternalLink, Info, Loader2, Database
} from "lucide-react";

/**
 * Renders a structured JSON table as an HTML table.
 */
function DataTable({ data }) {
  if (!data || data.length === 0) return null;
  
  const headers = data[0];
  const rows = data.slice(1, 6);

  return (
    <div className="mt-4 overflow-x-auto border border-gray-100 rounded-lg shadow-inner bg-gray-50/50">
      <table className="min-w-full divide-y divide-gray-200">
        <thead>
          <tr>
            {headers.map((cell, i) => (
              <th key={i} className="px-4 py-2 text-left text-[10px] font-bold text-gray-400 uppercase tracking-tight">
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-white/50 transition-colors">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-2 whitespace-nowrap text-[11px] text-gray-600">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length > 6 && (
        <div className="px-4 py-1 text-center text-[9px] text-gray-400 italic border-t border-gray-100">
          Showing 5 of {data.length} rows
        </div>
      )}
    </div>
  );
}

/**
 * Individual Search Result Card
 */
function ResultCard({ hit }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="group bg-white border border-gray-200 rounded-xl shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden">
      <div className="p-5">
        <div className="flex justify-between items-start mb-3">
          <div>
            <h2 className="text-lg font-bold text-gray-900 group-hover:text-blue-600 transition-colors leading-tight mb-1">
              {hit.event_name || "Untitled Meeting"}
            </h2>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-gray-500">
              <span className="inline-flex items-center gap-1 font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full">
                <MapPin className="w-3 h-3" /> {hit.city}, {hit.state}
              </span>
              <span className="inline-flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5" /> {hit.date ? new Date(hit.date).toLocaleDateString(undefined, { dateStyle: 'long' }) : "Unknown Date"}
              </span>
              <span className="inline-flex items-center gap-1 italic opacity-75">
                <FileText className="w-3.5 h-3.5" /> {hit.filename}
              </span>
            </div>
          </div>
          <button 
            onClick={() => setIsExpanded(!isExpanded)}
            className={`p-2 rounded-lg transition-colors ${isExpanded ? 'bg-blue-100 text-blue-600' : 'bg-gray-50 text-gray-400 hover:bg-gray-100 hover:text-gray-600'}`}
            title={isExpanded ? "Collapse Insights" : "Show AI Insights"}
          >
            {isExpanded ? <ChevronUp className="w-5 h-5" /> : <Sparkles className="w-5 h-5" />}
          </button>
        </div>

        {/* Search Snippet */}
        <div className="mb-4">
          {hit._formatted && hit._formatted.content ? (
            <p 
              className="text-gray-600 text-[13px] leading-relaxed line-clamp-3 group-hover:line-clamp-none transition-all"
              dangerouslySetInnerHTML={{
                __html: DOMPurify.sanitize(hit._formatted.content)
              }}
            />
          ) : (
            <p className="text-gray-600 text-[13px] line-clamp-3">{hit.content}</p>
          )}
        </div>

        {/* Collapsible Insights Section */}
        {isExpanded && (
          <div className="mt-4 pt-4 border-t border-gray-100 space-y-5 animate-in fade-in slide-in-from-top-2 duration-300">
            {/* AI Summary */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-purple-700 font-bold text-[10px] uppercase tracking-widest">
                <Sparkles className="w-3 h-3 text-purple-500" />
                AI-Generated Summary
              </div>
              <div className="p-4 bg-purple-50/50 border border-purple-100/50 rounded-xl">
                {hit.summary ? (
                  <p className="text-gray-800 text-[13px] whitespace-pre-line leading-relaxed italic">
                    {hit.summary}
                  </p>
                ) : (
                  <div className="flex items-center gap-2 text-gray-400 text-xs py-2">
                    <Info className="w-4 h-4" /> AI Summary is pending processing.
                  </div>
                )}
              </div>
            </div>

            {/* Entities (NLP) */}
            {hit.entities && (
              <div className="space-y-2">
                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Entities Mentioned</div>
                <div className="flex flex-wrap gap-2">
                  {(hit.entities.orgs || []).slice(0, 5).map((org, i) => (
                    <span key={`org-${i}`} className="inline-flex items-center gap-1 px-2 py-1 bg-white border border-gray-200 text-gray-700 text-[11px] rounded-lg shadow-sm">
                      <Building2 className="w-3 h-3 text-gray-400" /> {org}
                    </span>
                  ))}
                  {(hit.entities.locs || []).slice(0, 5).map((loc, i) => (
                    <span key={`loc-${i}`} className="inline-flex items-center gap-1 px-2 py-1 bg-white border border-gray-200 text-gray-700 text-[11px] rounded-lg shadow-sm">
                      <MapPin className="w-3 h-3 text-gray-400" /> {loc}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Tables */}
            {hit.tables && hit.tables.length > 0 && (
              <div className="space-y-2">
                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Data Extractions</div>
                {hit.tables.slice(0, 2).map((table, i) => (
                  <DataTable key={i} data={table} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Footer Actions */}
        <div className="mt-5 flex items-center justify-between">
          <a 
            href={hit.url} 
            target="_blank" 
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800 transition-colors"
          >
            Source PDF <ExternalLink className="w-3 h-3" />
          </a>
          {!isExpanded && (
            <button 
              onClick={() => setIsExpanded(true)}
              className="text-[10px] font-bold text-gray-400 hover:text-gray-600 transition-colors uppercase tracking-tight"
            >
              Analyze Result &rarr;
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  // Search State
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  
  // Filter State
  const [cityFilter, setCityFilter] = useState("");
  const [meetingTypeFilter, setMeetingTypeFilter] = useState("");
  const [stats, setStats] = useState(null);
  const [showFilters, setShowFilters] = useState(false);

  // Pilot cities list
  const cities = ["Belmont", "Berkeley", "Cupertino", "Dublin", "Fremont", "Hayward", "Moraga", "Mountain View", "Palo Alto", "San Mateo", "Sunnyvale"];

  const performSearch = useCallback(async (isLoadMore = false) => {
    if (!query.trim()) return;
    
    setLoading(true);
    if (!isLoadMore) setIsSearching(true);

    try {
      const currentOffset = isLoadMore ? offset + 20 : 0;
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      
      let url = `${apiUrl}/search?q=${encodeURIComponent(query)}&limit=20&offset=${currentOffset}`;
      if (cityFilter) url += `&city=${encodeURIComponent(cityFilter)}`;
      if (meetingTypeFilter) url += `&meeting_type=${encodeURIComponent(meetingTypeFilter)}`;

      const res = await fetch(url);
      const data = await res.json();
      
      const newHits = data.hits || [];
      setResults(prev => isLoadMore ? [...prev, ...newHits] : newHits);
      setOffset(currentOffset);
      setHasMore(newHits.length === 20); // If we got a full page, there might be more
    } catch (error) {
      console.error("Search failed:", error);
    } finally {
      setLoading(false);
      setIsSearching(false);
    }
  }, [query, cityFilter, meetingTypeFilter, offset]);

  // Handle auto-search when query or filters change
  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      setOffset(0);
      performSearch(false);
    }, 400);

    return () => clearTimeout(delayDebounceFn);
  }, [query, cityFilter, meetingTypeFilter]);

  // Initial stats fetch
  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${apiUrl}/stats`)
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(err => console.error("Stats fetch failed", err));
  }, []);

  return (
    <div className="min-h-screen bg-gray-50/50 flex flex-col">
      {/* Navbar / Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="bg-blue-600 p-1.5 rounded-lg shadow-sm">
              <Database className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-lg font-bold text-gray-900 tracking-tight">Town Council <span className="text-blue-600 font-medium">Insight</span></h1>
          </div>
          
          <div className="flex items-center gap-4">
            {stats && (
              <div className="hidden sm:flex items-center gap-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                <span>{stats.numberOfDocuments} Records</span>
                <span className="w-1 h-1 bg-gray-300 rounded-full"></span>
                <span>{cities.length} Cities</span>
              </div>
            )}
            <button 
              onClick={() => setShowFilters(!showFilters)}
              className={`p-2 rounded-lg transition-all border ${showFilters ? 'bg-blue-50 border-blue-200 text-blue-600' : 'bg-white border-gray-200 text-gray-500 hover:bg-gray-50'}`}
            >
              <Filter className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex-1 py-8 flex gap-8 relative">
        
        {/* Sidebar Filters (Desktop) / Dropdown (Mobile) */}
        <aside className={`${showFilters ? 'block' : 'hidden'} lg:block w-full lg:w-64 space-y-8 animate-in fade-in slide-in-from-left-4`}>
          <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm sticky top-24">
            <div className="flex items-center justify-between mb-6 lg:hidden">
              <h3 className="font-bold text-gray-900">Filters</h3>
              <button onClick={() => setShowFilters(false)}><X className="w-5 h-5 text-gray-400" /></button>
            </div>

            <div className="space-y-6">
              {/* City Filter */}
              <div>
                <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">Filter by City</label>
                <select 
                  value={cityFilter}
                  onChange={(e) => setCityFilter(e.target.value)}
                  className="block w-full text-sm border-gray-200 rounded-xl focus:ring-blue-500 focus:border-blue-500 bg-gray-50 py-2.5 px-3 transition-all"
                >
                  <option value="">All Municipalities</option>
                  {cities.map(c => <option key={c} value={c.toLowerCase()}>{c}</option>)}
                </select>
              </div>

              {/* Meeting Type (Common ones) */}
              <div>
                <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">Meeting Type</label>
                <div className="space-y-2">
                  {["Regular", "Special", "Closed"].map((type) => (
                    <label key={type} className="flex items-center gap-3 cursor-pointer group">
                      <input 
                        type="radio" 
                        name="meetingType"
                        checked={meetingTypeFilter === type}
                        onChange={() => setMeetingTypeFilter(type)}
                        className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                      />
                      <span className={`text-sm transition-colors ${meetingTypeFilter === type ? 'text-gray-900 font-semibold' : 'text-gray-500 group-hover:text-gray-700'}`}>
                        {type}
                      </span>
                    </label>
                  ))}
                  {meetingTypeFilter && (
                    <button 
                      onClick={() => setMeetingTypeFilter("")}
                      className="text-[10px] font-bold text-blue-600 uppercase hover:underline pt-2"
                    >
                      Clear Selection
                    </button>
                  )}
                </div>
              </div>

              {/* Reset All */}
              {(cityFilter || meetingTypeFilter) && (
                <div className="pt-4 border-t border-gray-100">
                  <button 
                    onClick={() => { setCityFilter(""); setMeetingTypeFilter(""); }}
                    className="w-full py-2 bg-gray-100 hover:bg-gray-200 text-gray-600 text-xs font-bold rounded-xl transition-colors"
                  >
                    Reset All Filters
                  </button>
                </div>
              )}
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <div className="flex-1 space-y-6">
          
          {/* Main Search Bar */}
          <div className="relative group">
            <div className="absolute inset-y-0 left-0 flex items-center pl-4 pointer-events-none">
              <Search className={`w-5 h-5 transition-colors ${query ? 'text-blue-500' : 'text-gray-400 group-focus-within:text-blue-500'}`} />
            </div>
            <input
              type="search"
              className="block w-full p-5 pl-12 text-base text-gray-900 border border-gray-200 rounded-2xl bg-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 shadow-sm transition-all placeholder:text-gray-400"
              placeholder="Search policies, budget items, or local laws..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {isSearching && (
              <div className="absolute inset-y-0 right-0 flex items-center pr-4">
                <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
              </div>
            )}
          </div>

          {/* Results Info */}
          {query && !loading && (
            <div className="flex items-center gap-2 px-2 text-xs font-medium text-gray-400 uppercase tracking-tight">
              Found {results.length} relevant results for "{query}"
            </div>
          )}

          {/* Results List */}
          <div className="space-y-6">
            {results.map((hit) => (
              <ResultCard key={hit.id} hit={hit} />
            ))}

            {/* Empty State */}
            {!query && !loading && (
              <div className="text-center py-20 bg-white border border-gray-100 rounded-3xl shadow-sm">
                <div className="max-w-xs mx-auto space-y-4">
                  <div className="bg-gray-50 w-16 h-16 rounded-full flex items-center justify-center mx-auto">
                    <Search className="w-8 h-8 text-gray-300" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-gray-900">Start your search</h3>
                    <p className="text-sm text-gray-500 leading-relaxed mt-1">
                      Search for zoning changes, housing updates, or environmental policies across the Bay Area.
                    </p>
                  </div>
                  <div className="flex flex-wrap justify-center gap-2 pt-2">
                    {["Zoning", "Rent Control", "Bike Lanes", "Parks"].map(tag => (
                      <button 
                        key={tag} 
                        onClick={() => setQuery(tag)}
                        className="px-3 py-1 bg-white border border-gray-200 text-gray-600 text-[11px] font-bold rounded-full hover:border-blue-300 hover:text-blue-600 transition-all shadow-sm"
                      >
                        {tag}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {query && !loading && results.length === 0 && (
              <div className="text-center py-20 bg-white border border-gray-100 rounded-3xl shadow-sm">
                <div className="max-w-xs mx-auto space-y-2">
                  <div className="text-4xl">🔍</div>
                  <h3 className="text-base font-bold text-gray-900">No matches found</h3>
                  <p className="text-sm text-gray-500 leading-relaxed">
                    Try broadening your search terms or adjusting the filters in the sidebar.
                  </p>
                </div>
              </div>
            )}

            {/* Load More Button */}
            {hasMore && (
              <div className="pt-8 text-center">
                <button 
                  onClick={() => performSearch(true)}
                  disabled={loading}
                  className="inline-flex items-center gap-2 px-8 py-3 bg-white border border-gray-200 text-gray-700 text-sm font-bold rounded-2xl hover:bg-gray-50 transition-all shadow-sm disabled:opacity-50"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Load More Documents"}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 py-10 mt-12">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p className="text-xs text-gray-400 font-medium tracking-tight uppercase">
            Data provided by Data4Democracy Town Council Insight &copy; 2026
          </p>
        </div>
      </footer>
    </div>
  );
}