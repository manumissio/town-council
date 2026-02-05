import { useState, useRef, useEffect } from "react";
import { Search, ChevronDown, X, Loader2, MapPin, Building2, Tag, Filter } from "lucide-react";

/**
 * FilterDropdown Component
 * 
 * A sleek, minimal dropdown that sits INSIDE the search bar unit.
 */
function FilterDropdown({ label, value, options, onChange, placeholder, icon: Icon }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative flex-1 min-w-0" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full flex flex-col px-6 py-3 text-left transition-all hover:bg-gray-50 group border-l border-gray-100 first:border-l-0 ${isOpen ? 'bg-gray-50' : ''}`}
      >
        <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">{label}</span>
        <div className="flex items-center gap-2">
          {Icon && <Icon className={`w-3.5 h-3.5 shrink-0 ${value ? 'text-blue-600' : 'text-gray-300'}`} />}
          <span className={`text-[13px] font-bold truncate ${value ? 'text-gray-900' : 'text-gray-400'}`}>
            {value ? options.find(o => o.value.toLowerCase() === value.toLowerCase())?.label || value : placeholder}
          </span>
          <ChevronDown className={`w-3.5 h-3.5 text-gray-300 ml-auto transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 w-full mt-1 bg-white border border-gray-100 rounded-2xl shadow-2xl z-50 py-2 animate-in fade-in slide-in-from-top-1 duration-200 max-h-64 overflow-y-auto">
          <div 
            onClick={() => { onChange(""); setIsOpen(false); }}
            className="px-4 py-2 text-[10px] font-black text-gray-400 hover:bg-gray-50 cursor-pointer uppercase tracking-widest border-b border-gray-50 mb-1"
          >
            All {label}s
          </div>
          {options.map((opt) => (
            <div
              key={opt.value}
              onClick={() => { onChange(opt.value); setIsOpen(false); }}
              className={`px-4 py-3 text-[13px] font-medium cursor-pointer transition-colors ${value?.toLowerCase() === opt.value.toLowerCase() ? 'bg-blue-50 text-blue-700 font-bold' : 'text-gray-700 hover:bg-gray-50'}`}
            >
              {opt.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * SearchHub Component
 * 
 * Restores the 'Original' sleek search bar look but embeds filters directly into it.
 * This satisfies both 'Resemble what it used to be' and 'Incorporate filters'.
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
    <section className="bg-white border-b border-gray-100 py-16 lg:py-24 shadow-inner relative z-20">
      <div className="max-w-5xl mx-auto px-4">
        
        {/* The Unified Search Bar (Resembling the original sleek look) */}
        <div className="bg-white border-2 border-gray-100 rounded-[3rem] shadow-2xl hover:shadow-[0_20px_60px_rgba(0,0,0,0.08)] transition-all duration-500 overflow-hidden group focus-within:ring-8 focus-within:ring-blue-500/5 focus-within:border-blue-400">
          
          {/* Main Input Row */}
          <div className="flex items-center relative border-b border-gray-50">
            <div className="absolute left-8 pointer-events-none text-gray-300 group-focus-within:text-blue-500 transition-colors">
              <Search className="w-7 h-7" />
            </div>
            <input
              type="search"
              autoFocus
              className="w-full py-8 pl-20 pr-20 text-2xl font-bold tracking-tight text-gray-900 bg-transparent border-none focus:ring-0 placeholder:text-gray-300"
              placeholder="Search meeting records..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div className="absolute right-6 flex items-center gap-4">
              {isSearching && <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />}
              {(query || cityFilter || orgFilter || meetingTypeFilter) && (
                <button 
                  onClick={resetApp}
                  className="p-3 bg-gray-50 hover:bg-red-50 text-red-400 hover:text-red-600 rounded-full transition-all group/reset"
                  title="Clear all"
                >
                  <X className="w-5 h-5 group-hover/reset:rotate-90 transition-transform" />
                </button>
              )}
            </div>
          </div>

          {/* Filter Row (Integrated directly into the bottom of the bar) */}
          <div className="flex flex-col lg:flex-row items-stretch bg-gray-50/30">
            <FilterDropdown 
              label="Where"
              placeholder="All Cities"
              value={cityFilter}
              options={availableCities.map(c => ({ label: c, value: c.toLowerCase() }))}
              onChange={setCityFilter}
              icon={MapPin}
            />
            <FilterDropdown 
              label="Body"
              placeholder="All Bodies"
              value={orgFilter}
              options={availableOrgs.map(o => ({ label: o, value: o }))}
              onChange={setOrgFilter}
              icon={Building2}
            />
            <FilterDropdown 
              label="Type"
              placeholder="Any Type"
              value={meetingTypeFilter}
              options={[
                { label: "Regular", value: "Regular" },
                { label: "Special", value: "Special" },
                { label: "Closed", value: "Closed" }
              ]}
              onChange={setMeetingTypeFilter}
              icon={Tag}
            />
          </div>
        </div>

        {/* Quick Search Tags */}
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          {["Zoning", "Housing", "Budget", "Police"].map(tag => (
            <button 
              key={tag} 
              onClick={() => setQuery(tag)}
              className="px-6 py-2 bg-white border border-gray-200 text-gray-500 text-[11px] font-black uppercase tracking-widest rounded-full hover:border-blue-400 hover:text-blue-600 hover:shadow-lg transition-all active:scale-95"
            >
              {tag}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}