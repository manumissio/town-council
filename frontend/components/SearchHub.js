import { useState, useRef, useEffect } from "react";
import { Search, ChevronDown, X, Loader2, MapPin, Building2, Tag } from "lucide-react";

/**
 * SegmentedDropdown Component
 * 
 * A sleek, borderless segment within the search bar that acts as a filter.
 */
function SegmentedDropdown({ label, value, options, onChange, placeholder, icon: Icon }) {
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
    <div className="relative flex-1 min-w-[120px] hidden md:flex" ref={dropdownRef}>
      {/* Vertical Divider */}
      <div className="w-px h-8 bg-gray-100 self-center" />
      
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex-1 flex flex-col px-5 py-3 text-left transition-all hover:bg-gray-50 group ${isOpen ? 'bg-gray-50' : ''}`}
      >
        <span className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-0.5">{label}</span>
        <div className="flex items-center gap-1.5">
          <span className={`text-[12px] font-bold truncate ${value ? 'text-blue-600' : 'text-gray-500'}`}>
            {value ? options.find(o => o.value.toLowerCase() === value.toLowerCase())?.label || value : placeholder}
          </span>
          <ChevronDown className={`w-3 h-3 text-gray-300 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {isOpen && (
        <div className="absolute top-full right-0 w-64 mt-2 bg-white border border-gray-100 rounded-2xl shadow-2xl z-50 py-2 animate-in fade-in slide-in-from-top-1 duration-200 overflow-hidden">
          <div 
            onClick={() => { onChange(""); setIsOpen(false); }}
            className="px-4 py-2 text-[10px] font-black text-gray-300 hover:bg-gray-50 cursor-pointer uppercase tracking-widest border-b border-gray-50 mb-1"
          >
            Clear {label}
          </div>
          <div className="max-h-60 overflow-y-auto">
            {options.map((opt) => (
              <div
                key={opt.value}
                onClick={() => { onChange(opt.value); setIsOpen(false); }}
                className={`px-4 py-2.5 text-[13px] font-medium cursor-pointer transition-colors ${value?.toLowerCase() === opt.value.toLowerCase() ? 'bg-blue-50 text-blue-700 font-bold' : 'text-gray-600 hover:bg-gray-50'}`}
              >
                {opt.label}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * SearchHub Component
 * 
 * DESIGN GOAL: Restore the 'Original' wide, sleek search bar look but
 * embed the filters as segments on the RIGHT side of the same row.
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
      <div className="max-w-6xl mx-auto px-4">
        
        {/* The Unified Search Bar (SINGLE ROW DESIGN) */}
        <div className="bg-white border-2 border-gray-100 rounded-full shadow-2xl hover:shadow-[0_20px_60px_rgba(0,0,0,0.1)] transition-all duration-500 flex items-stretch group focus-within:ring-8 focus-within:ring-blue-500/5 focus-within:border-blue-400">
          
          {/* Main Keyword Search Segment */}
          <div className="flex-[2] flex items-center relative min-w-0">
            <div className="absolute left-8 pointer-events-none text-gray-300 group-focus-within:text-blue-500 transition-colors">
              <Search className="w-6 h-6" />
            </div>
            <input
              type="search"
              autoFocus
              className="w-full py-7 pl-18 pr-4 text-lg font-bold tracking-tight text-gray-900 bg-transparent border-none focus:ring-0 placeholder:text-gray-300"
              placeholder="Search meeting records..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          {/* Integrated Filter Segments (Only shown on Desktop/Tablet) */}
          <SegmentedDropdown 
            label="Where"
            placeholder="Municipality"
            value={cityFilter}
            options={availableCities.map(c => ({ label: c, value: c.toLowerCase() }))}
            onChange={setCityFilter}
          />

          <SegmentedDropdown 
            label="Body"
            placeholder="Legislative Body"
            value={orgFilter}
            options={availableOrgs.map(o => ({ label: o, value: o }))}
            onChange={setOrgFilter}
          />

          {/* Reset Button (Integrated at the end) */}
          <div className="flex items-center pr-2 pl-2">
            {isSearching ? (
              <div className="p-4"><Loader2 className="w-5 h-5 text-blue-500 animate-spin" /></div>
            ) : (query || cityFilter || orgFilter || meetingTypeFilter) ? (
              <button 
                onClick={resetApp}
                className="p-4 bg-gray-50 hover:bg-red-50 text-red-400 hover:text-red-600 rounded-full transition-all group/reset"
                title="Reset Search"
              >
                <X className="w-5 h-5 group-hover/reset:rotate-90 transition-transform" />
              </button>
            ) : (
              <div className="w-12 h-12" /> // Spacer
            )}
          </div>
        </div>

        {/* Mobile Filter Row (Only visible when stacked) */}
        <div className="flex md:hidden mt-4 gap-2 overflow-x-auto pb-2 scrollbar-hide">
           {availableCities.length > 0 && (
             <select 
               value={cityFilter} 
               onChange={(e) => setCityFilter(e.target.value)}
               className="bg-white border border-gray-200 rounded-xl px-4 py-2 text-xs font-bold text-gray-600"
             >
               <option value="">All Cities</option>
               {availableCities.map(c => <option key={c} value={c.toLowerCase()}>{c}</option>)}
             </select>
           )}
           <select 
             value={meetingTypeFilter} 
             onChange={(e) => setMeetingTypeFilter(e.target.value)}
             className="bg-white border border-gray-200 rounded-xl px-4 py-2 text-xs font-bold text-gray-600"
           >
             <option value="">All Types</option>
             {["Regular", "Special", "Closed"].map(t => <option key={t} value={t}>{t}</option>)}
           </select>
        </div>

        {/* Quick Search Tags */}
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          {["Zoning", "Housing", "Budget", "Police"].map(tag => (
            <button 
              key={tag} 
              onClick={() => setQuery(tag)}
              className="px-6 py-2.5 bg-white border border-gray-200 text-gray-500 text-[11px] font-black uppercase tracking-widest rounded-full hover:border-blue-400 hover:text-blue-600 hover:shadow-lg transition-all"
            >
              {tag}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
