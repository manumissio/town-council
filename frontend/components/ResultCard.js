import { useState } from "react";
import DOMPurify from "isomorphic-dompurify";
import { 
  MapPin, Calendar, FileText, ExternalLink, ChevronUp, ChevronDown, 
  Sparkles, Building2, UserCircle, Table as TableIcon, Loader2
} from "lucide-react";
import DataTable from "./DataTable";

/**
 * ResultCard Component
 * 
 * DESIGN: Uses a tabbed interface for Full Text, AI Summary, and Structured Agenda.
 * All AI features are "On-Demand" to minimize API costs and respect rate limits.
 */
export default function ResultCard({ hit, onPersonClick }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [viewMode, setViewMode] = useState("text"); // 'text', 'summary', 'agenda'
  
  const [summary, setSummary] = useState(hit.summary);
  const [agendaItems, setAgendaItems] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSegmenting, setIsSegmenting] = useState(false);

  const isAgendaItem = hit.result_type === 'agenda_item';

  const handleGenerateSummary = async () => {
    if (!hit.catalog_id) return;
    
    setIsGenerating(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/summarize/${hit.catalog_id}`, { method: "POST" });
      const data = await res.json();
      
      if (data.summary) {
        setSummary(data.summary);
      }
    } catch (err) {
      console.error("AI Generation failed", err);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleGenerateAgenda = async () => {
    if (!hit.catalog_id) return;
    
    setIsSegmenting(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/segment/${hit.catalog_id}`, { method: "POST" });
      const data = await res.json();
      
      if (data.items) {
        setAgendaItems(data.items);
      }
    } catch (err) {
      console.error("Agenda segmentation failed", err);
    } finally {
      setIsSegmenting(false);
    }
  };

  return (
    <div className={`group bg-white border rounded-2xl shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden text-left ${isAgendaItem ? 'border-blue-100 ring-1 ring-blue-50/50' : 'border-gray-200'}`}>
      <div className="p-6">
        <div className="flex justify-between items-start mb-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 mb-1">
               {isAgendaItem && (
                 <span className="bg-blue-600 text-white text-[9px] font-black uppercase tracking-tighter px-1.5 py-0.5 rounded flex items-center gap-1 shadow-sm">
                   <Sparkles className="w-2.5 h-2.5" /> Agenda Item
                 </span>
               )}
               <h2 className="text-xl font-bold text-gray-900 group-hover:text-blue-600 transition-colors leading-tight cursor-pointer" onClick={() => setIsExpanded(!isExpanded)}>
                {isAgendaItem ? (hit._formatted?.title || hit.title) : (hit.event_name || "Untitled Meeting")}
              </h2>
            </div>
            
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[13px] text-gray-500">
              <span className="inline-flex items-center gap-1.5 font-bold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-lg uppercase tracking-wider text-[10px]">
                <MapPin className="w-3 h-3" /> {hit.city}
              </span>
              {isAgendaItem && (
                <>
                  <span className="text-gray-400 italic">Part of: {hit.event_name}</span>
                  {hit.classification && (
                    <span className="bg-purple-50 text-purple-600 px-2 py-0.5 rounded text-[10px] font-bold uppercase">{hit.classification}</span>
                  )}
                  {hit.result && (
                    <span className="bg-green-50 text-green-600 px-2 py-0.5 rounded text-[10px] font-bold uppercase">{hit.result}</span>
                  )}
                </>
              )}
              <span className="inline-flex items-center gap-1.5">
                <Calendar className="w-4 h-4 text-gray-400" /> {hit.date ? new Date(hit.date).toLocaleDateString(undefined, { dateStyle: 'long' }) : "Unknown Date"}
              </span>
              {!isAgendaItem && (
                <span className="inline-flex items-center gap-1.5 opacity-75">
                  <FileText className="w-4 h-4 text-gray-400" /> {hit.filename}
                </span>
              )}
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

        {hit.people_metadata && hit.people_metadata.length > 0 && (
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mr-1">Officials:</span>
            {hit.people_metadata.slice(0, 5).map((person) => (
              <button 
                key={person.id}
                onClick={() => onPersonClick(person.id)}
                className="inline-flex items-center gap-1 px-2.5 py-1 bg-white border border-gray-200 text-gray-600 text-[11px] font-bold rounded-lg hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50 transition-all shadow-sm"
              >
                <UserCircle className="w-3.5 h-3.5" />
                {person.name}
              </button>
            ))}
            {hit.people_metadata.length > 5 && (
              <span className="text-[10px] text-gray-400 italic">+{hit.people_metadata.length - 5} more</span>
            )}
          </div>
        )}

        {!isExpanded && (
          <div className="mb-2">
            {isAgendaItem ? (
              <p 
                className="text-gray-600 text-sm leading-relaxed line-clamp-3"
                dangerouslySetInnerHTML={{
                  __html: DOMPurify.sanitize(hit._formatted?.description || hit.description || "No description available.")
                }}
              />
            ) : (
              hit._formatted && hit._formatted.content ? (
                <p 
                  className="text-gray-600 text-sm leading-relaxed line-clamp-3"
                  dangerouslySetInnerHTML={{
                    __html: DOMPurify.sanitize(hit._formatted.content)
                  }}
                />
              ) : (
                <p className="text-gray-600 text-sm line-clamp-3">{hit.content}</p>
              )
            )}
          </div>
        )}

        {isExpanded && (
          <div className="mt-6 space-y-6 animate-in fade-in slide-in-from-top-2 duration-300">
            <div className="flex items-center justify-between p-2 bg-gray-50 rounded-2xl border border-gray-100">
              <div className="flex gap-1 p-1 bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
                <button 
                  onClick={() => setViewMode("text")}
                  className={`px-4 py-2 text-xs font-bold rounded-lg transition-all whitespace-nowrap ${viewMode === "text" ? 'bg-blue-600 text-white shadow-sm' : 'text-gray-500 hover:bg-gray-50'}`}
                >
                  Full Text
                </button>
                <button 
                  onClick={() => setViewMode("summary")}
                  className={`px-4 py-2 text-xs font-bold rounded-lg transition-all flex items-center gap-2 whitespace-nowrap ${viewMode === "summary" ? 'bg-purple-600 text-white shadow-sm' : 'text-gray-500 hover:bg-gray-50'}`}
                >
                  <Sparkles className={`w-3.5 h-3.5 ${viewMode === "summary" ? 'text-white' : 'text-purple-500'}`} />
                  AI Summary
                </button>
                {!isAgendaItem && (
                  <button 
                    onClick={() => setViewMode("agenda")}
                    className={`px-4 py-2 text-xs font-bold rounded-lg transition-all flex items-center gap-2 whitespace-nowrap ${viewMode === "agenda" ? 'bg-indigo-600 text-white shadow-sm' : 'text-gray-500 hover:bg-gray-50'}`}
                  >
                    <TableIcon className={`w-3.5 h-3.5 ${viewMode === "agenda" ? 'text-white' : 'text-indigo-500'}`} />
                    Structured Agenda
                  </button>
                )}
              </div>
              <span className="hidden sm:block px-4 text-[10px] font-bold text-gray-400 uppercase tracking-widest">
                {viewMode === "text" ? "OCR Extraction" : "Gemini AI"}
              </span>
            </div>

            <div className="relative">
              {viewMode === "summary" ? (
                <div className="p-8 bg-purple-50/30 border border-purple-100 rounded-3xl space-y-6">
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-purple-700 font-bold text-[11px] uppercase tracking-widest">
                      <Sparkles className="w-4 h-4" />
                      Executive Summary
                    </div>
                    {summary ? (
                      <div className="space-y-4">
                        <span className="bg-purple-100 text-purple-700 text-[9px] font-black uppercase px-1.5 py-0.5 rounded shadow-sm">Gemini 2.0 AI</span>
                        <p className="text-gray-800 text-[15px] whitespace-pre-line leading-relaxed italic">
                          {summary}
                        </p>
                      </div>
                    ) : hit.summary_extractive ? (
                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <span className="bg-indigo-100 text-indigo-700 text-[9px] font-black uppercase px-1.5 py-0.5 rounded shadow-sm">Local Fast-Pass AI</span>
                          <button 
                            onClick={handleGenerateSummary}
                            disabled={isGenerating}
                            className="text-[10px] font-bold text-purple-600 hover:text-purple-800 flex items-center gap-1 transition-colors"
                          >
                            <Sparkles className="w-3 h-3" /> Upgrade to Gemini AI
                          </button>
                        </div>
                        <p className="text-gray-700 text-[14px] leading-relaxed line-clamp-6">
                          {hit.summary_extractive}
                        </p>
                      </div>
                    ) : (
                      <div className="py-6 flex flex-col items-center justify-center border-2 border-dashed border-purple-200 rounded-3xl bg-white/50">
                        <div className="mb-4 bg-purple-100 p-3 rounded-full">
                          <Sparkles className="w-6 h-6 text-purple-600" />
                        </div>
                        <h4 className="font-bold text-purple-900 mb-1">No summary yet</h4>
                        <p className="text-purple-600/60 text-xs mb-6 max-w-[240px] text-center">
                          Generate an executive summary using local or cloud AI.
                        </p>
                        <button 
                          onClick={handleGenerateSummary}
                          disabled={isGenerating}
                          className="px-6 py-2.5 bg-purple-600 text-white text-xs font-bold rounded-xl shadow-lg shadow-purple-200 hover:bg-purple-700 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                          {isGenerating ? (
                            <><Loader2 className="w-4 h-4 animate-spin" /> Reading...</>
                          ) : (
                            <><Sparkles className="w-3.5 h-3.5" /> Generate Gemini Summary</>
                          )}
                        </button>
                      </div>
                    )}
                  </div>

                  {(hit.entities || hit.topics) && (
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
                  )}
                </div>
              ) : viewMode === "agenda" ? (
                <div className="p-8 bg-indigo-50/30 border border-indigo-100 rounded-3xl space-y-6">
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-indigo-700 font-bold text-[11px] uppercase tracking-widest">
                      <TableIcon className="w-4 h-4" />
                      Segmented Agenda Items
                    </div>
                    {agendaItems ? (
                      <div className="grid gap-4">
                        {agendaItems.map((item, i) => (
                          <div key={i} className="p-4 bg-white border border-indigo-100 rounded-2xl shadow-sm">
                            <div className="flex items-start gap-3">
                              <span className="bg-indigo-100 text-indigo-700 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0">{item.order || i+1}</span>
                              <div className="space-y-1">
                                <h5 className="font-bold text-gray-900 text-sm">{item.title}</h5>
                                <p className="text-xs text-gray-600 leading-relaxed">{item.description}</p>
                                <div className="flex gap-2 pt-1">
                                  {item.classification && <span className="text-[9px] font-black uppercase text-indigo-400">{item.classification}</span>}
                                  {item.result && <span className="text-[9px] font-black uppercase text-green-500">• {item.result}</span>}
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="py-12 flex flex-col items-center justify-center border-2 border-dashed border-indigo-200 rounded-3xl bg-white/50">
                        <div className="mb-4 bg-indigo-100 p-3 rounded-full">
                          <TableIcon className="w-6 h-6 text-indigo-600" />
                        </div>
                        <h4 className="font-bold text-indigo-900 mb-1">Agenda not segmented</h4>
                        <p className="text-indigo-600/60 text-xs mb-6 max-w-[240px] text-center">
                          Use AI to split this document into individual, searchable agenda items.
                        </p>
                        <button 
                          onClick={handleGenerateAgenda}
                          disabled={isSegmenting}
                          className="px-6 py-2.5 bg-indigo-600 text-white text-xs font-bold rounded-xl shadow-lg shadow-indigo-200 hover:bg-indigo-700 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                          {isSegmenting ? (
                            <><Loader2 className="w-4 h-4 animate-spin" /> Splitting...</>
                          ) : (
                            <><Sparkles className="w-3.5 h-3.5" /> Segment Agenda Items</>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="p-8 bg-gray-50/50 border border-gray-100 rounded-3xl">
                  <div className="prose prose-sm max-w-none text-gray-700 max-h-[500px] overflow-y-auto pr-4 scrollbar-thin scrollbar-thumb-gray-200 text-left">
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

        {!isExpanded && (
          <div className="mt-4 pt-4 border-t border-gray-50 flex justify-end px-2 pb-2">
            <button 
              onClick={() => setIsExpanded(true)}
              className="text-[11px] font-bold text-blue-600 hover:text-blue-800 transition-colors uppercase tracking-widest flex items-center gap-1 group/btn px-4 py-2"
            >
              View Full Text <ChevronDown className="w-3.5 h-3.5 group-hover/btn:translate-y-0.5 transition-transform" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}