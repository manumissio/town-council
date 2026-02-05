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
      <div className="max-w-6xl mx-auto px-4">
        {/* Unified Search Hub Container */}
        <div className="bg-white border border-gray-200 rounded-[2rem] shadow-xl hover:shadow-2xl transition-all duration-300 overflow-hidden flex flex-col lg:flex-row items-stretch group focus-within:ring-8 focus-within:ring-blue-500/5 focus-within:border-blue-400">
          
          {/* 1. Keyword Search Segment (The widest part) */}
          <div className="flex-[2] flex items-center relative min-w-0">
            <div className="absolute left-7 pointer-events-none">
              <Search className={`w-5 h-5 transition-colors ${query ? 'text-blue-500' : 'text-gray-400 group-focus-within:text-blue-500'}`} />
            </div>
            <input
              type="search"
              autoFocus
              className="w-full py-7 pl-16 pr-4 text-lg text-gray-900 bg-transparent border-none focus:ring-0 placeholder:text-gray-400 font-medium"
              placeholder="Search meeting notes, policies, or keywords..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {isSearching && (
              <div className="absolute right-4 flex items-center">
                <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
              </div>
            )}
          </div>

          {/* Vertical Dividers (Hidden on mobile) */}
          <div className="hidden lg:block w-px bg-gray-100 my-6" />

          {/* 2. Municipality Segment */}
          <div className="flex-1 min-w-0 px-6 py-4 lg:py-0 flex items-center hover:bg-gray-50/80 transition-colors cursor-pointer border-t border-gray-50 lg:border-none">
            <div className="flex flex-col w-full text-left">
              <label className="text-[10px] font-black text-gray-400 uppercase tracking-[0.15em] mb-1">Where</label>
              <div className="relative flex items-center">
                <select 
                  value={cityFilter}
                  onChange={(e) => setCityFilter(e.target.value)}
                  className="bg-transparent border-none p-0 text-[13px] font-bold text-gray-800 focus:ring-0 cursor-pointer appearance-none w-full"
                >
                  <option value="">All Bay Area</option>
                  {availableCities.map(c => <option key={c} value={c.toLowerCase()}>{c}</option>)}
                </select>
                <ChevronDown className="w-3.5 h-3.5 text-gray-400 ml-auto pointer-events-none" />
              </div>
            </div>
          </div>

          <div className="hidden lg:block w-px bg-gray-100 my-6" />

          {/* 3. Organization Segment */}
          <div className="flex-1 min-w-0 px-6 py-4 lg:py-0 flex items-center hover:bg-gray-50/80 transition-colors cursor-pointer border-t border-gray-50 lg:border-none">
            <div className="flex flex-col w-full text-left">
              <label className="text-[10px] font-black text-gray-400 uppercase tracking-[0.15em] mb-1">Body</label>
              <div className="relative flex items-center">
                <select 
                  value={orgFilter}
                  onChange={(e) => setOrgFilter(e.target.value)}
                  className="bg-transparent border-none p-0 text-[13px] font-bold text-gray-800 focus:ring-0 cursor-pointer appearance-none w-full"
                >
                  <option value="">All Bodies</option>
                  {availableOrgs.map(o => <option key={o} value={o}>{o}</option>)}
                </select>
                <ChevronDown className="w-3.5 h-3.5 text-gray-400 ml-auto pointer-events-none" />
              </div>
            </div>
          </div>

          <div className="hidden lg:block w-px bg-gray-100 my-6" />

          {/* 4. Category Segment */}
          <div className="flex-1 min-w-0 px-6 py-4 lg:py-0 flex items-center hover:bg-gray-50/80 transition-colors cursor-pointer border-t border-gray-50 lg:border-none">
            <div className="flex flex-col w-full text-left">
              <label className="text-[10px] font-black text-gray-400 uppercase tracking-[0.15em] mb-1">Type</label>
              <div className="relative flex items-center">
                <select 
                  value={meetingTypeFilter}
                  onChange={(e) => setMeetingTypeFilter(e.target.value)}
                  className="bg-transparent border-none p-0 text-[13px] font-bold text-gray-800 focus:ring-0 cursor-pointer appearance-none w-full"
                >
                  <option value="">Any Type</option>
                  {["Regular", "Special", "Closed"].map(type => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
                <ChevronDown className="w-3.5 h-3.5 text-gray-400 ml-auto pointer-events-none" />
              </div>
            </div>
          </div>

          {/* Global Reset Button */}
          {(cityFilter || meetingTypeFilter || orgFilter || query) && (
            <button 
              onClick={resetApp}
              className="lg:border-l border-gray-100 px-8 py-5 lg:py-0 bg-white hover:bg-red-50 text-red-500 transition-colors flex items-center justify-center group/reset shrink-0"
              title="Reset all filters"
            >
              <X className="w-5 h-5 group-hover/reset:rotate-90 transition-all duration-300" />
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
