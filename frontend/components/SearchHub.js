import { Search, X, Loader2, ChevronDown } from "lucide-react";

/**
 * SearchHub Component
 * 
 * RESTORATION: This version restores the absolute original 'Sleek' design.
 * It uses a single, massive, horizontal bar where filters are integrated
 * as minimal segments without excessive labels or complex dropdowns.
 */
export default function SearchHub({ 
  query, setQuery, 
  cityFilter, setCityFilter, 
  orgFilter, setOrgFilter,
  meetingTypeFilter, setMeetingTypeFilter,
  includeAgendaItems, setIncludeAgendaItems,
  searchMode, setSearchMode,
  sortMode, setSortMode,
  availableCities, availableOrgs,
  isSearching, resetApp
}) {
  const cycleSortMode = () => {
    const current = (sortMode || "newest").toLowerCase();
    if (current === "newest") return setSortMode("oldest");
    if (current === "oldest") return setSortMode("relevance");
    return setSortMode("newest");
  };

  const sortLabel = (() => {
    const current = (sortMode || "newest").toLowerCase();
    if (current === "oldest") return "Sort: Oldest";
    if (current === "relevance") return "Sort: Relevance";
    return "Sort: Newest";
  })();

  return (
    <section className="bg-white border-b border-gray-100 py-16 lg:py-24 shadow-inner relative z-20">
      <div className="max-w-6xl mx-auto px-4">
        
        {/* The Unified Search Hub (Original Horizontal Layout) */}
        <div className="bg-white border-2 border-gray-100 rounded-[3rem] shadow-2xl hover:shadow-[0_20px_60px_rgba(0,0,0,0.1)] transition-all duration-500 overflow-hidden flex flex-col lg:flex-row items-stretch group focus-within:ring-8 focus-within:ring-blue-500/5 focus-within:border-blue-400">
          
          {/* 1. Keyword Search Segment (The widest part) */}
          <div className="flex-[2] flex items-center relative min-w-0">
            <div className="absolute left-8 pointer-events-none text-gray-300 group-focus-within:text-blue-500 transition-colors">
              <Search className="w-6 h-6" />
            </div>
            <input
              type="search"
              autoFocus
              className="w-full py-8 pl-20 pr-4 text-xl font-bold tracking-tight text-gray-900 bg-transparent border-none focus:ring-0 placeholder:text-gray-300"
              placeholder="Search meeting records..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          <div className="hidden lg:block w-px bg-gray-100 my-6" />

          {/* 2. Municipality Segment */}
          <div className="flex-1 min-w-0 px-6 py-4 lg:py-0 flex items-center hover:bg-gray-50/80 transition-colors cursor-pointer border-t border-gray-50 lg:border-none relative">
            <select 
              value={cityFilter}
              onChange={(e) => setCityFilter(e.target.value)}
              className="bg-transparent border-none p-0 pr-8 text-[13px] font-black uppercase tracking-widest text-gray-500 focus:ring-0 cursor-pointer appearance-none w-full"
            >
              <option value="">Everywhere</option>
              {availableCities.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <ChevronDown className="absolute right-6 w-4 h-4 text-gray-300 pointer-events-none" />
          </div>

          <div className="hidden lg:block w-px bg-gray-100 my-6" />

          {/* 3. Organization Segment */}
          <div className="flex-1 min-w-0 px-6 py-4 lg:py-0 flex items-center hover:bg-gray-50/80 transition-colors cursor-pointer border-t border-gray-50 lg:border-none relative">
            <select 
              value={orgFilter}
              onChange={(e) => setOrgFilter(e.target.value)}
              className="bg-transparent border-none p-0 pr-8 text-[13px] font-black uppercase tracking-widest text-gray-500 focus:ring-0 cursor-pointer appearance-none w-full"
            >
              <option value="">All Bodies</option>
              {availableOrgs.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
            <ChevronDown className="absolute right-6 w-4 h-4 text-gray-300 pointer-events-none" />
          </div>

          <div className="hidden lg:block w-px bg-gray-100 my-6" />

          {/* 4. Category Segment */}
          <div className="flex-1 min-w-0 px-6 py-4 lg:py-0 flex items-center hover:bg-gray-50/80 transition-colors cursor-pointer border-t border-gray-50 lg:border-none relative">
            <select 
              value={meetingTypeFilter}
              onChange={(e) => setMeetingTypeFilter(e.target.value)}
              className="bg-transparent border-none p-0 pr-8 text-[13px] font-black uppercase tracking-widest text-gray-500 focus:ring-0 cursor-pointer appearance-none w-full"
            >
              <option value="">All Types</option>
              {["Regular", "Special", "Closed", "Other"].map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-6 w-4 h-4 text-gray-300 pointer-events-none" />
          </div>

          {/* Global Reset Button */}
          {(cityFilter || meetingTypeFilter || orgFilter || query) && (
            <button 
              onClick={resetApp}
              className="lg:border-l border-gray-100 px-8 py-5 lg:py-0 bg-white hover:bg-red-50 text-red-400 hover:text-red-600 transition-colors flex items-center justify-center group/reset shrink-0"
              title="Reset all filters"
            >
              <X className="w-6 h-6 group-hover/reset:rotate-90 transition-all duration-300" />
            </button>
          )}

          {isSearching && (
            <div className="px-8 flex items-center justify-center border-l border-gray-100 bg-gray-50">
              <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
            </div>
          )}
        </div>

        {/* Quick Search Tags */}
        <div className="mt-10 flex flex-wrap justify-center gap-3 items-center">
          <button
            type="button"
            onClick={() => setSearchMode(searchMode === "semantic" ? "keyword" : "semantic")}
            className={`px-5 py-2.5 border text-[11px] font-black uppercase tracking-widest rounded-full transition-all ${
              searchMode === "semantic"
                ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                : "bg-white text-gray-500 border-gray-200 hover:border-indigo-400 hover:text-indigo-600"
            }`}
            title="Semantic mode uses vector similarity instead of keyword matching."
          >
            {searchMode === "semantic" ? "Mode: Semantic" : "Mode: Keyword"}
          </button>
          <button
            type="button"
            onClick={() => setIncludeAgendaItems(!includeAgendaItems)}
            className={`px-5 py-2.5 border text-[11px] font-black uppercase tracking-widest rounded-full transition-all ${
              includeAgendaItems
                ? "bg-blue-600 text-white border-blue-600 shadow-sm"
                : "bg-white text-gray-500 border-gray-200 hover:border-blue-400 hover:text-blue-600"
            }`}
            title="When enabled, search results can include individual agenda items as separate hits."
          >
            {includeAgendaItems ? "Agenda Items: On" : "Agenda Items: Off"}
          </button>
          {searchMode !== "semantic" ? (
            <button
              type="button"
              onClick={cycleSortMode}
              className="px-5 py-2.5 border text-[11px] font-black uppercase tracking-widest rounded-full transition-all bg-white text-gray-500 border-gray-200 hover:border-blue-400 hover:text-blue-600"
              title="Cycle sort mode: newest, oldest, relevance."
            >
              {sortLabel}
            </button>
          ) : (
            <span
              className="px-5 py-2.5 border text-[11px] font-black uppercase tracking-widest rounded-full bg-gray-100 text-gray-400 border-gray-200"
              title="Sort is disabled in semantic mode (ranked by semantic score)."
            >
              Sort: Semantic
            </span>
          )}
          {["Zoning", "Housing", "Budget", "Police", "Biking"].map(tag => (
            <button 
              key={tag} 
              onClick={() => setQuery(tag)}
              className="px-6 py-2.5 bg-white border border-gray-200 text-gray-500 text-[11px] font-black uppercase tracking-widest rounded-full hover:border-blue-400 hover:text-blue-600 transition-all"
            >
              {tag}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
