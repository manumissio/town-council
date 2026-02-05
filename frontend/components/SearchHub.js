import { Search, ChevronDown, X, Loader2 } from "lucide-react";

/**
 * SearchHub Component
 * 
 * This is the main interaction area. 
 * Instead of a separate sidebar, we use a 'Segmented' design:
 * Segment 1: The text you want to find.
 * Segment 2: The City ('Where').
 * Segment 3: The Body ('Department').
 * Segment 4: The Meeting Type ('Type').
 */
export default function SearchHub({ 
  query, setQuery, 
  cityFilter, setCityFilter, 
  orgFilter, setOrgFilter,
  meetingTypeFilter, setMeetingTypeFilter,
  availableCities, availableOrgs,
  isSearching, resetApp
}) {
  return (
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
            {isSearching && (
              <div className="absolute inset-y-0 right-0 flex items-center pr-4">
                <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
              </div>
            )}
          </div>

          <div className="hidden md:block w-px bg-gray-100 my-4" />

          {/* 2. Municipality Segment */}
          <div className="relative group/segment px-6 py-4 md:py-0 flex items-center min-w-[200px] hover:bg-gray-50 transition-colors cursor-pointer">
            <div className="flex flex-col w-full">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-0.5 text-left">Where</label>
              <select 
                value={cityFilter}
                onChange={(e) => setCityFilter(e.target.value)}
                className="bg-transparent border-none p-0 text-sm font-bold text-gray-800 focus:ring-0 cursor-pointer appearance-none w-full"
              >
                <option value="">All Bay Area</option>
                {availableCities.map(c => <option key={c} value={c.toLowerCase()}>{c}</option>)}
              </select>
            </div>
            <ChevronDown className="w-4 h-4 text-gray-400 ml-2" />
          </div>

          <div className="hidden md:block w-px bg-gray-100 my-4" />

          {/* 3. Organization Segment */}
          <div className="relative group/segment px-6 py-4 md:py-0 flex items-center min-w-[200px] hover:bg-gray-50 transition-colors cursor-pointer">
            <div className="flex flex-col w-full">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-0.5 text-left">Body</label>
              <select 
                value={orgFilter}
                onChange={(e) => setOrgFilter(e.target.value)}
                className="bg-transparent border-none p-0 text-sm font-bold text-gray-800 focus:ring-0 cursor-pointer appearance-none w-full"
              >
                <option value="">All Bodies</option>
                {availableOrgs.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            </div>
            <ChevronDown className="w-4 h-4 text-gray-400 ml-2" />
          </div>

          <div className="hidden md:block w-px bg-gray-100 my-4" />

          {/* 4. Category Segment */}
          <div className="relative group/segment px-6 py-4 md:py-0 flex items-center min-w-[160px] hover:bg-gray-50 transition-colors cursor-pointer">
            <div className="flex flex-col w-full">
              <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-0.5 text-left">Type</label>
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

          {/* Global Reset */}
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
  );
}
