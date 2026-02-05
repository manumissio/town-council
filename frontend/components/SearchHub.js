import { useState, useRef, useEffect } from "react";
import { Search, ChevronDown, X, Loader2, MapPin, Building2, Tag } from "lucide-react";

/**
 * CustomDropdown Component
 * 
 * A polished, accessible replacement for the standard <select> tag.
 * It ensures the 'Search Hub' segments look consistent and premium.
 */
function CustomDropdown({ label, value, options, onChange, placeholder, icon: Icon }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
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
        className={`w-full flex items-center gap-3 px-6 py-4 lg:py-0 h-full text-left transition-all hover:bg-gray-50/80 group ${isOpen ? 'bg-gray-50' : ''}`}
      >
        <div className="flex flex-col min-w-0 flex-1">
          <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-0.5">{label}</span>
          <div className="flex items-center gap-2">
            {Icon && <Icon className={`w-3.5 h-3.5 shrink-0 ${value ? 'text-blue-500' : 'text-gray-300'}`} />}
            <span className={`text-[13px] font-bold truncate ${value ? 'text-gray-900' : 'text-gray-400'}`}>
              {value ? options.find(o => o.value.toLowerCase() === value.toLowerCase())?.label || value : placeholder}
            </span>
          </div>
        </div>
        <ChevronDown className={`w-4 h-4 text-gray-300 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 w-full mt-2 bg-white border border-gray-100 rounded-2xl shadow-2xl z-50 py-2 animate-in fade-in slide-in-from-top-2 duration-200 max-h-60 overflow-y-auto overflow-x-hidden">
          <div 
            onClick={() => { onChange(""); setIsOpen(false); }}
            className="px-4 py-2 text-xs font-bold text-gray-400 hover:bg-gray-50 cursor-pointer uppercase tracking-tight"
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
 * This is the primary search interface.
 * It uses a single, high-impact bar to house both keywords and filters.
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
    <section className="bg-white border-b border-gray-100 py-12 lg:py-20 shadow-inner relative z-20">
      <div className="max-w-6xl mx-auto px-4">
        
        {/* Main Search Bar Container */}
        <div className="bg-white border border-gray-200 rounded-[2.5rem] shadow-2xl hover:shadow-[0_20px_50px_rgba(0,0,0,0.1)] transition-all duration-500 overflow-hidden flex flex-col lg:flex-row items-stretch group focus-within:ring-8 focus-within:ring-blue-500/5 focus-within:border-blue-400">
          
          {/* 1. Keyword Segment */}
          <div className="flex-[2] flex items-center relative min-w-0 border-b lg:border-b-0 border-gray-50">
            <div className="absolute left-8 pointer-events-none">
              <Search className={`w-6 h-6 transition-colors duration-300 ${query ? 'text-blue-500' : 'text-gray-300 group-focus-within:text-blue-500'}`} />
            </div>
            <input
              type="search"
              autoFocus
              className="w-full py-8 pl-18 pr-6 text-xl text-gray-900 bg-transparent border-none focus:ring-0 placeholder:text-gray-300 font-bold tracking-tight"
              placeholder="Search meeting records..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {isSearching && (
              <div className="absolute right-6 flex items-center">
                <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
              </div>
            )}
          </div>

          {/* Segment Dividers (Desktop Only) */}
          <div className="hidden lg:block w-px bg-gray-100 my-8" />

          {/* 2. City Segment */}
          <CustomDropdown 
            label="Where"
            placeholder="All Cities"
            value={cityFilter}
            options={availableCities.map(c => ({ label: c, value: c.toLowerCase() }))}
            onChange={setCityFilter}
            icon={MapPin}
          />

          <div className="hidden lg:block w-px bg-gray-100 my-8" />

          {/* 3. Body Segment */}
          <CustomDropdown 
            label="Body"
            placeholder="All Bodies"
            value={orgFilter}
            options={availableOrgs.map(o => ({ label: o, value: o }))}
            onChange={setOrgFilter}
            icon={Building2}
          />

          <div className="hidden lg:block w-px bg-gray-100 my-8" />

          {/* 4. Type Segment */}
          <CustomDropdown 
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

          {/* Global Reset Segment */}
          {(cityFilter || meetingTypeFilter || orgFilter || query) && (
            <div className="flex items-center border-t lg:border-t-0 lg:border-l border-gray-100">
              <button 
                onClick={resetApp}
                className="w-full lg:w-20 py-6 lg:py-0 h-full bg-white hover:bg-red-50 text-red-400 hover:text-red-600 transition-all flex items-center justify-center group/reset"
                title="Clear all"
              >
                <X className="w-6 h-6 group-hover/reset:rotate-90 transition-transform duration-300" />
              </button>
            </div>
          )}
        </div>

        {/* Quick Search Tags */}
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          {["Zoning", "Housing", "Budget", "Police"].map(tag => (
            <button 
              key={tag} 
              onClick={() => setQuery(tag)}
              className="px-6 py-2.5 bg-white border border-gray-200 text-gray-500 text-[11px] font-black uppercase tracking-widest rounded-full hover:border-blue-400 hover:text-blue-600 hover:shadow-lg hover:shadow-blue-500/5 transition-all active:scale-95"
            >
              {tag}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}