import { useState, useRef, useEffect } from "react";
import { Search, ChevronDown, X, Loader2, MapPin, Building2, Tag, Filter } from "lucide-react";

/**
 * FilterPill Component
 * 
 * A clean, rounded dropdown button that sits underneath the main search bar.
 * This keeps the search bar wide and 'nice' while incorporating filters into the hub.
 */
function FilterPill({ label, value, options, onChange, placeholder, icon: Icon }) {
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
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-5 py-2.5 rounded-full border-2 transition-all text-xs font-bold uppercase tracking-wider shadow-sm ${
          value 
            ? 'bg-blue-600 border-blue-600 text-white shadow-blue-100' 
            : 'bg-white border-gray-100 text-gray-500 hover:border-blue-200 hover:text-blue-600'
        }`}
      >
        {Icon && <Icon className={`w-3.5 h-3.5 ${value ? 'text-blue-100' : ''}`} />}
        <span>{value ? options.find(o => o.value.toLowerCase() === value.toLowerCase())?.label || value : placeholder}</span>
        <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-2 min-w-[200px] bg-white border border-gray-100 rounded-2xl shadow-2xl z-50 py-2 animate-in fade-in slide-in-from-top-2 duration-200">
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
 * SearchHub Component (Refined)
 * 
 * This design restores the wide, elegant search bar from the earlier version
 * and integrates the filters as a row of premium interactive pills underneath.
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
      <div className="max-w-4xl mx-auto px-4">
        
        {/* Row 1: The Main Hero Search Bar */}
        <div className="relative group mb-8">
          <div className="absolute inset-y-0 left-0 flex items-center pl-8 pointer-events-none text-gray-300 group-focus-within:text-blue-500 transition-colors">
            <Search className="w-7 h-7" />
          </div>
          <input
            type="search"
            autoFocus
            className="block w-full py-8 pl-20 pr-20 text-2xl font-bold tracking-tight text-gray-900 border-2 border-gray-100 rounded-[3rem] bg-gray-50/30 focus:bg-white focus:ring-8 focus:ring-blue-500/5 focus:border-blue-500 shadow-xl transition-all placeholder:text-gray-300"
            placeholder="Search meeting records..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="absolute inset-y-0 right-0 flex items-center pr-6">
            {isSearching ? (
              <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
            ) : (query || cityFilter || orgFilter || meetingTypeFilter) && (
              <button 
                onClick={resetApp}
                className="p-3 bg-white hover:bg-red-50 text-red-400 hover:text-red-600 rounded-full transition-all group/reset"
                title="Reset all"
              >
                <X className="w-6 h-6 group-hover/reset:rotate-90 transition-transform" />
              </button>
            )}
          </div>
        </div>

        {/* Row 2: Integrated Filter Pills */}
        <div className="flex flex-wrap items-center justify-center gap-3">
          <div className="flex items-center gap-2 mr-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Filter By</span>
          </div>
          
          <FilterPill 
            label="City"
            placeholder="Municipality"
            value={cityFilter}
            options={availableCities.map(c => ({ label: c, value: c.toLowerCase() }))}
            onChange={setCityFilter}
            icon={MapPin}
          />

          <FilterPill 
            label="Body"
            placeholder="Legislative Body"
            value={orgFilter}
            options={availableOrgs.map(o => ({ label: o, value: o }))}
            onChange={setOrgFilter}
            icon={Building2}
          />

          <FilterPill 
            label="Type"
            placeholder="Meeting Type"
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

        {/* Quick Search Tags */}
        <div className="mt-12 flex flex-wrap justify-center gap-2 pt-8 border-t border-gray-50">
          <span className="w-full text-center text-[10px] font-bold text-gray-300 uppercase tracking-[0.2em] mb-4">Common Topics</span>
          {["Zoning", "Housing", "Budget", "Police", "Environment", "Bike Lanes"].map(tag => (
            <button 
              key={tag} 
              onClick={() => setQuery(tag)}
              className="px-5 py-2 bg-white border border-gray-100 text-gray-500 text-[11px] font-black uppercase tracking-widest rounded-full hover:border-blue-400 hover:text-blue-600 hover:shadow-lg transition-all"
            >
              {tag}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
