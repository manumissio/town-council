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
 * ResultCard Component
 * 
 * How it works for a developer:
 * 1. Tier 1 (Initial View): Shows only basic info and a short 3-line preview.
 * 2. Tier 2 (Expanded View): When you click 'View Full Text', it reveals the full OCR content.
 * 3. Tier 3 (AI View): Within the expanded card, you can toggle the 'AI Insights' 
 *    button to switch from the raw text to the Gemini-generated summary.
 */
function ResultCard({ hit }) {
  const [isExpanded, setIsExpanded] = useState(false); // Controls if the card is open or closed
  const [showSummary, setShowSummary] = useState(false); // Controls if we show OCR text or the AI Summary

  return (
    <div className="group bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden">
      <div className="p-6">
        <div className="flex justify-between items-start mb-4">
          <div className="space-y-1.5">
            <h2 className="text-xl font-bold text-gray-900 group-hover:text-blue-600 transition-colors leading-tight">
              {hit.event_name || "Untitled Meeting"}
            </h2>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[13px] text-gray-500">
              <span className="inline-flex items-center gap-1.5 font-bold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-lg uppercase tracking-wider text-[10px]">
                <MapPin className="w-3 h-3" /> {hit.city}, {hit.state}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Calendar className="w-4 h-4 text-gray-400" /> {hit.date ? new Date(hit.date).toLocaleDateString(undefined, { dateStyle: 'long' }) : "Unknown Date"}
              </span>
              <span className="inline-flex items-center gap-1.5 opacity-75">
                <FileText className="w-4 h-4 text-gray-400" /> {hit.filename}
              </span>
            </div>
          </div>
          
          <div className="flex gap-2">
            <a 
              href={hit.url} 
              target="_blank" 
              rel="noopener noreferrer"
              className="p-2.5 bg-gray-50 text-gray-400 hover:bg-blue-50 hover:text-blue-600 rounded-xl transition-all border border-transparent hover:border-blue-100"
              title="Open Original PDF"
            >
              <ExternalLink className="w-5 h-5" />
            </a>
            <button 
              onClick={() => setIsExpanded(!isExpanded)}
              className={`p-2.5 rounded-xl transition-all border ${isExpanded ? 'bg-blue-600 text-white border-blue-600 shadow-lg shadow-blue-200' : 'bg-gray-50 text-gray-400 hover:bg-gray-100 hover:text-gray-600 border-transparent'}`}
              title={isExpanded ? "Collapse Document" : "Expand Document Text"}
            >
              {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Tier 1: Search Snippet (Always visible) */}
        {!isExpanded && (
          <div className="mb-2">
            {hit._formatted && hit._formatted.content ? (
              <p 
                className="text-gray-600 text-sm leading-relaxed line-clamp-3"
                dangerouslySetInnerHTML={{
                  __html: DOMPurify.sanitize(hit._formatted.content)
                }}
              />
            ) : (
              <p className="text-gray-600 text-sm line-clamp-3">{hit.content}</p>
            )}
          </div>
        )}

        {/* Tier 2: Expanded Full Text View */}
        {isExpanded && (
          <div className="mt-6 space-y-6 animate-in fade-in slide-in-from-top-2 duration-300">
            
            {/* Action Bar for Expanded View */}
            <div className="flex items-center justify-between p-2 bg-gray-50 rounded-2xl border border-gray-100">
              <div className="flex gap-1 p-1 bg-white rounded-xl border border-gray-100 shadow-sm">
                <button 
                  onClick={() => setShowSummary(false)}
                  className={`px-4 py-2 text-xs font-bold rounded-lg transition-all ${!showSummary ? 'bg-blue-600 text-white shadow-sm' : 'text-gray-500 hover:bg-gray-50'}`}
                >
                  Full Document Text
                </button>
                <button 
                  onClick={() => setShowSummary(true)}
                  className={`px-4 py-2 text-xs font-bold rounded-lg transition-all flex items-center gap-2 ${showSummary ? 'bg-purple-600 text-white shadow-sm' : 'text-gray-500 hover:bg-gray-50'}`}
                >
                  <Sparkles className={`w-3.5 h-3.5 ${showSummary ? 'text-white' : 'text-purple-500'}`} />
                  AI Insights
                </button>
              </div>
              <span className="px-4 text-[10px] font-bold text-gray-400 uppercase tracking-widest">
                {showSummary ? "Gemini 2.0 Flash" : "OCR Extraction"}
              </span>
            </div>

            {/* Content Display Area */}
            <div className="relative">
              {showSummary ? (
                /* AI Summary View */
                <div className="p-8 bg-purple-50/30 border border-purple-100 rounded-3xl space-y-6">
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-purple-700 font-bold text-[11px] uppercase tracking-widest">
                      <Sparkles className="w-4 h-4" />
                      Executive Summary
                    </div>
                    {hit.summary ? (
                      <p className="text-gray-800 text-[15px] whitespace-pre-line leading-relaxed italic">
                        {hit.summary}
                      </p>
                    ) : (
                      <div className="flex items-center gap-3 text-gray-400 text-sm py-4">
                        <Info className="w-5 h-5" /> Summary is being generated by the pipeline.
                      </div>
                    )}
                  </div>

                  {/* Entities (NLP) and Topics */}
                  <div className="grid md:grid-cols-2 gap-6 pt-6 border-t border-purple-100">
                    {hit.entities && (
                      <div className="space-y-3">
                        <div className="text-[10px] font-bold text-purple-400 uppercase tracking-widest">Entities Mentioned</div>
                        <div className="flex flex-wrap gap-2">
                          {(hit.entities.orgs || []).slice(0, 8).map((org, i) => (
                            <span key={`org-${i}`} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-white border border-purple-100 text-gray-700 text-[11px] rounded-xl shadow-sm font-medium">
                              <Building2 className="w-3.5 h-3.5 text-purple-400" /> {org}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {hit.topics && hit.topics.length > 0 && (
                      <div className="space-y-3">
                        <div className="text-[10px] font-bold text-purple-400 uppercase tracking-widest">Discovered Topics</div>
                        <div className="flex flex-wrap gap-2">
                          {hit.topics.map((topic, i) => (
                            <span key={i} className="px-3 py-1.5 bg-purple-100/50 text-purple-700 text-[11px] font-bold rounded-xl border border-purple-200 uppercase tracking-tight">
                              #{topic}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                /* Full Text View */
                <div className="p-8 bg-gray-50/50 border border-gray-100 rounded-3xl">
                  <div className="prose prose-sm max-w-none text-gray-700 max-h-[500px] overflow-y-auto pr-4 scrollbar-thin scrollbar-thumb-gray-200">
                    <div className="flex items-center gap-2 mb-6 text-gray-400 font-bold text-[10px] uppercase tracking-widest">
                      <FileText className="w-4 h-4" />
                      OCR Extracted Content
                    </div>
                    {hit._formatted && hit._formatted.content ? (
                      <div 
                        className="whitespace-pre-line leading-relaxed text-[14px]"
                        dangerouslySetInnerHTML={{
                          __html: DOMPurify.sanitize(hit._formatted.content)
                        }}
                      />
                    ) : (
                      <p className="whitespace-pre-line leading-relaxed text-[14px]">{hit.content}</p>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Tables (Always shown at bottom if present) */}
            {hit.tables && hit.tables.length > 0 && (
              <div className="space-y-4 pt-4 border-t border-gray-100">
                <div className="flex items-center gap-2 text-gray-400 font-bold text-[10px] uppercase tracking-widest">
                  <TableIcon className="w-4 h-4" />
                  Structured Data Tables ({hit.tables.length})
                </div>
                {hit.tables.slice(0, 3).map((table, i) => (
                  <DataTable key={i} data={table} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Footer Toggle (Only show if not expanded) */}
        {!isExpanded && (
          <div className="mt-4 pt-4 border-t border-gray-50 flex justify-end">
            <button 
              onClick={() => setIsExpanded(true)}
              className="text-[11px] font-bold text-blue-600 hover:text-blue-800 transition-colors uppercase tracking-widest flex items-center gap-1 group/btn"
            >
              View Full Text <ChevronDown className="w-3.5 h-3.5 group-hover/btn:translate-y-0.5 transition-transform" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function Home() {
  // Search State
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [totalHits, setTotalHits] = useState(0); // Track the total results found by the engine
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  
  // Filter State
  const [cityFilter, setCityFilter] = useState("");
  const [meetingTypeFilter, setMeetingTypeFilter] = useState("");
  const [orgFilter, setOrgFilter] = useState("");

  // Pilot cities list
  const cities = ["Belmont", "Berkeley", "Cupertino", "Dublin", "Fremont", "Hayward", "Moraga", "Mountain View", "Palo Alto", "San Mateo", "Sunnyvale"];
  const organizations = ["City Council", "Planning Commission", "Parks & Recreation Commission"];

  const performSearch = useCallback(async (isLoadMore = false) => {
    /**
     * The heart of the search UI.
     * It talks to our FastAPI backend and handles both new searches 
     * and "Load More" requests.
     */
    if (!query.trim()) return;
    
    setLoading(true);
    if (!isLoadMore) setIsSearching(true);

    try {
      // Offset tells the API which "page" of results we want (0, 20, 40, etc.)
      const currentOffset = isLoadMore ? offset + 20 : 0;
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      
      // Build the URL with our search query and any active filters
      let url = `${apiUrl}/search?q=${encodeURIComponent(query)}&limit=20&offset=${currentOffset}`;
      if (cityFilter) url += `&city=${encodeURIComponent(cityFilter)}`;
      if (meetingTypeFilter) url += `&meeting_type=${encodeURIComponent(meetingTypeFilter)}`;
      if (orgFilter) url += `&org=${encodeURIComponent(orgFilter)}`;

      const res = await fetch(url);
      const data = await res.json();
      
      const newHits = data.hits || [];
      
      // Update results: append if loading more, otherwise replace
      setResults(prev => isLoadMore ? [...prev, ...newHits] : newHits);
      
      // Store the total number of hits so the user knows how many documents match in total
      setTotalHits(data.estimatedTotalHits || 0);
      
      setOffset(currentOffset);
      
      // If we got exactly 20 results, there's likely more data to load.
      setHasMore(newHits.length === 20); 
    } catch (error) {
      console.error("Search failed:", error);
    } finally {
      setLoading(false);
      setIsSearching(false);
    }
  }, [query, cityFilter, meetingTypeFilter, orgFilter, offset]);

  // Debouncing: This prevents the app from searching on EVERY single keypress.
  // It waits for you to stop typing for 400ms before asking the server for data.
  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      setOffset(0); // Reset to first page when query/filters change
      performSearch(false);
    }, 400);

    return () => clearTimeout(delayDebounceFn);
  }, [query, cityFilter, meetingTypeFilter, orgFilter]);

  // Function to reset the application to its initial state
  // Why: This allows the user to go back to the "Start Search" screen without
  // having to reload the whole website in their browser.
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

      <div className="min-h-screen bg-gray-50/50 flex flex-col">

        {/* Navbar / Header */}

        {/* Note: 'sticky top-0' keeps the header visible even when you scroll down */}

        <header className="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-sm">

          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">

            <div className="flex items-center gap-8">

              {/* Logo and Title: Clicking this resets everything back to the start */}

              <div className="flex items-center gap-2 cursor-pointer group" onClick={resetApp}>

                <div className="bg-blue-600 p-1.5 rounded-lg shadow-sm group-hover:bg-blue-700 transition-colors">

                  <Database className="w-5 h-5 text-white" />

                </div>

                <h1 className="text-lg font-bold text-gray-900 tracking-tight">Town Council <span className="text-blue-600 font-medium">Insight</span></h1>

              </div>

              

              {/* Desktop Navigation Links */}

              <nav className="hidden md:flex items-center gap-6">

                {/* Reset the app state locally instead of using an <a> tag to avoid slow page reloads */}

                <button onClick={resetApp} className="text-sm font-semibold text-blue-600 border-b-2 border-blue-600 pb-1">Search</button>

                

                {/* Links to the project's source code and external standards documentation */}

                <a href="https://github.com/manumissio/town-council" target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-gray-500 hover:text-blue-600 transition-colors">GitHub</a>

                              <a href="https://open-civic-data.readthedocs.io/en/latest/index.html" target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-gray-500 hover:text-blue-600 transition-colors">Standards</a>

                            </nav>

                          </div>

                        </div>

                      </header>

                

  

              {/* Unified Search Hub Section */}

                

  

              {/* 

                

  

                This is the main interaction area. 

                

  

                Instead of a separate sidebar, we use a 'Segmented' design:

                

  

                Segment 1: The text you want to find.

                

  

                Segment 2: The City ('Where').

                

  

                Segment 3: The Meeting Type ('Type').

                

  

              */}

                

  

              <section className="bg-white border-b border-gray-100 py-16 shadow-inner relative z-20">

                

  

        

          <div className="max-w-5xl mx-auto px-4">

            <div className="bg-white border-2 border-gray-100 rounded-[2rem] shadow-xl hover:shadow-2xl transition-all duration-300 overflow-hidden flex flex-col md:flex-row items-stretch group focus-within:border-blue-500 focus-within:ring-8 focus-within:ring-blue-500/5">

              

              {/* 1. Keyword Search Segment */}

              <div className="flex-1 flex items-center relative min-w-[300px]">

                <div className="absolute left-6 pointer-events-none">

                  <Search className={`w-5 h-5 transition-colors ${query ? 'text-blue-500' : 'text-gray-400 group-focus-within:text-blue-500'}`} />

                </div>

                <input

                  type="search"

                  autoFocus

                  className="w-full py-6 pl-14 pr-4 text-lg text-gray-900 bg-transparent border-none focus:ring-0 placeholder:text-gray-400 font-medium"

                  placeholder="Search meeting notes..."

                  value={query}

                  onChange={(e) => setQuery(e.target.value)}

                />

              </div>

  

              <div className="hidden md:block w-px bg-gray-100 my-4" />

  

              {/* 2. Municipality Segment */}

              <div className="relative group/segment px-6 py-4 md:py-0 flex items-center min-w-[200px] hover:bg-gray-50 transition-colors cursor-pointer">

                <div className="flex flex-col w-full">

                  <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-0.5">Where</label>

                  <select 

                    value={cityFilter}

                    onChange={(e) => setCityFilter(e.target.value)}

                    className="bg-transparent border-none p-0 text-sm font-bold text-gray-800 focus:ring-0 cursor-pointer appearance-none w-full"

                  >

                    <option value="">All Bay Area</option>

                    {cities.map(c => <option key={c} value={c.toLowerCase()}>{c}</option>)}

                  </select>

                </div>

                <ChevronDown className="w-4 h-4 text-gray-400 ml-2" />

              </div>

  

              <div className="hidden md:block w-px bg-gray-100 my-4" />

  

                          {/* 3. Organization Segment */}

  

                          <div className="relative group/segment px-6 py-4 md:py-0 flex items-center min-w-[200px] hover:bg-gray-50 transition-colors cursor-pointer">

  

                            <div className="flex flex-col w-full">

  

                              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-0.5">Body</label>

  

                              <select 

  

                                value={orgFilter}

  

                                onChange={(e) => setOrgFilter(e.target.value)}

  

                                className="bg-transparent border-none p-0 text-sm font-bold text-gray-800 focus:ring-0 cursor-pointer appearance-none w-full"

  

                              >

  

                                <option value="">All Bodies</option>

  

                                {organizations.map(o => <option key={o} value={o}>{o}</option>)}

  

                              </select>

  

                            </div>

  

                            <ChevronDown className="w-4 h-4 text-gray-400 ml-2" />

  

                          </div>

  

              

  

                          <div className="hidden md:block w-px bg-gray-100 my-4" />

  

              

  

                          {/* 4. Category Segment */}

  

                          <div className="relative group/segment px-6 py-4 md:py-0 flex items-center min-w-[160px] hover:bg-gray-50 transition-colors cursor-pointer">

  

                            <div className="flex flex-col w-full">

  

                              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-0.5">Type</label>

  

                              <select 

  

                                value={meetingTypeFilter}

  

                                onChange={(e) => setMeetingTypeFilter(e.target.value)}

  

                                className="bg-transparent border-none p-0 text-sm font-bold text-gray-800 focus:ring-0 cursor-pointer appearance-none w-full"

  

                              >

  

                                <option value="">Any Type</option>

  

                                {["Regular", "Special", "Closed"].map(type => (

  

                                  <option key={type} value={type}>{type}</option>

  

                                ))}

  

                              </select>

  

                            </div>

  

                            <ChevronDown className="w-4 h-4 text-gray-400 ml-2" />

  

                          </div>

  

              

  

                          {/* Global Reset (Visible only when filters are active) */}

  

                          {(cityFilter || meetingTypeFilter || orgFilter || query) && (

  

                            <button 

  

                              onClick={resetApp}

  

                              className="md:border-l border-gray-100 px-6 py-4 md:py-0 bg-white hover:bg-red-50 text-red-500 transition-colors flex items-center justify-center group/reset"

  

                              title="Reset Search"

  

                            >

  

                              <X className="w-5 h-5 group-hover/reset:rotate-90 transition-transform" />

  

                            </button>

  

                          )}

  

                        </div>

  

                        

  

                        {/* Quick Shortcuts */}

  

                        <div className="mt-8 flex flex-wrap justify-center gap-3">

  

                          {["Zoning", "Housing", "Budget", "Police"].map(tag => (

  

                            <button 

  

                              key={tag} 

  

                              onClick={() => setQuery(tag)}

  

                              className="px-5 py-2 bg-white border border-gray-200 text-gray-600 text-[11px] font-bold rounded-full hover:border-blue-400 hover:text-blue-600 transition-all shadow-sm active:scale-95"

  

                            >

  

                              {tag}

  

                            </button>

  

                          ))}

  

                        </div>

  

                      </div>

  

                    </section>

  

              

  

                    <div className="max-w-5xl mx-auto px-4 py-12 flex-1 relative">

  

                      <div className="space-y-8">

  

                        

  

                        {/* Results Info */}

  

                        {query && !loading && (

  

                          <div className="flex items-center justify-between mb-2">

  

                             <div className="flex items-center gap-2 text-sm font-bold text-gray-400 uppercase tracking-widest">

  

                              <Database className="w-4 h-4" /> Found {totalHits} relevant records

  

                            </div>

  

                            {/* Display active filter chips for quick feedback */}

  

                            <div className="flex gap-2">

  

                              {cityFilter && <span className="text-[10px] font-bold bg-blue-50 text-blue-600 px-2 py-1 rounded uppercase">{cityFilter}</span>}

  

                              {orgFilter && <span className="text-[10px] font-bold bg-purple-50 text-purple-600 px-2 py-1 rounded uppercase">{orgFilter}</span>}

  

                              {meetingTypeFilter && <span className="text-[10px] font-bold bg-gray-100 text-gray-600 px-2 py-1 rounded uppercase">{meetingTypeFilter}</span>}

  

                            </div>

  

                          </div>

  

                        )}

  

              

  

            {/* Results List */}

            <div className="space-y-8">

              {results.map((hit) => (

                <ResultCard key={hit.id} hit={hit} />

              ))}

  

          

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
      <footer className="bg-white border-t border-gray-200 py-12 mt-12">
        <div className="max-w-5xl mx-auto px-4 text-center">
          <p className="text-[11px] text-gray-400 font-bold tracking-widest uppercase mb-2">
            Town Council Insight
          </p>
          <p className="text-sm text-gray-500 max-w-2xl mx-auto leading-relaxed">
            An open-source initiative originally launched in 2017 by Data for Democracy to improve civic transparency and provide public access to local government records.
          </p>
        </div>
      </footer>
    </div>
  );
}