import { useState, useEffect, useMemo } from "react";
import DOMPurify from "isomorphic-dompurify";
import { 
  MapPin, Calendar, FileText, ExternalLink, ChevronUp, ChevronDown, 
  Sparkles, Building2, UserCircle, Table as TableIcon, Loader2, Link2,
  Flag, AlertCircle, CheckCircle
} from "lucide-react";
import DataTable from "./DataTable";
import { API_BASE_URL, buildApiUrl, getApiHeaders, isDemoMode } from "../lib/api";
import textFormatter from "../lib/textFormatter";

const { renderFormattedExtractedText } = textFormatter;

// Poll background tasks until complete/failed.
async function pollTaskStatus(taskId, callback, onError, type = "summary") {
  const checkStatus = async () => {
    try {
      const res = await fetch(buildApiUrl(`/tasks/${taskId}`));
      const data = await res.json();

      if (data.status === "complete") {
        if (type === "summary") callback(data.result || {});
        else if (type === "agenda") callback(data.result.items || []);
        else if (type === "topics") callback(data.result || {});
        else callback(data.result);
        return true;
      }

      if (data.status === "failed") {
        console.error("Task failed", data.error);
        if (onError) onError(data.error);
        return true;
      }

      return false;
    } catch (err) {
      console.error("Polling error", err);
      if (onError) onError(err);
      return true;
    }
  };

  const interval = setInterval(async () => {
    const isDone = await checkStatus();
    if (isDone) clearInterval(interval);
  }, 2000);
}

/**
 * ResultCard Component
 * 
 * DESIGN: Uses a tabbed interface for Full Text, AI Summary, and Structured Agenda.
 * All AI features are "On-Demand" to minimize API costs and respect rate limits.
 */
export default function ResultCard({ hit, onPersonClick, onTopicClick }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showAllOfficials, setShowAllOfficials] = useState(false);
  const [viewMode, setViewMode] = useState("text"); // 'text', 'summary', 'agenda'
  
  const [summary, setSummary] = useState(hit.summary);
  const [topics, setTopics] = useState(hit.topics || []);
  const [summaryBlockReason, setSummaryBlockReason] = useState(null);
  const [topicsBlockReason, setTopicsBlockReason] = useState(null);
  const [agendaItems, setAgendaItems] = useState(hit.agenda_items || null);
  const [relatedMeetings, setRelatedMeetings] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isTaggingTopics, setIsTaggingTopics] = useState(false);
  const [isSegmenting, setIsSegmenting] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractedTextOverride, setExtractedTextOverride] = useState(null);
  const [isLoadingCanonicalText, setIsLoadingCanonicalText] = useState(false);
  const [canonicalTextLoadError, setCanonicalTextLoadError] = useState(null);
  const [canonicalTextFetchFailed, setCanonicalTextFetchFailed] = useState(false);
  const [derivedStatus, setDerivedStatus] = useState(null);
  const [isLoadingRelated, setIsLoadingRelated] = useState(false);
  const [isReporting, setIsReporting] = useState(false);
  const [reportStatus, setReportStatus] = useState(null); // 'loading', 'success', 'error'
  const demoMode = isDemoMode();
  const canMutate = !demoMode && Boolean(process.env.NEXT_PUBLIC_API_AUTH_KEY);

  // Readability is a display concern only: keep DB content raw, format in UI.
  const fullTextSource = useMemo(() => {
    // Use the canonical DB text when we have it, even if it's empty:
    // an empty string means "not extracted yet" (common after startup purge).
    if (typeof extractedTextOverride === "string") return extractedTextOverride;

    // Only fall back to the search snippet when we could not fetch canonical text.
    if (canonicalTextFetchFailed && typeof hit.content === "string") return hit.content;
    return "";
  }, [extractedTextOverride, canonicalTextFetchFailed, hit.content]);

  const formattedFullTextHtml = useMemo(() => {
    return renderFormattedExtractedText(fullTextSource);
  }, [fullTextSource]);

  const isAgendaItem = hit.result_type === 'agenda_item';
  const summaryIsStale = (derivedStatus && derivedStatus.summary_is_stale) ?? hit.summary_is_stale ?? false;
  const topicsIsStale = (derivedStatus && derivedStatus.topics_is_stale) ?? hit.topics_is_stale ?? false;
  const summaryNotGeneratedYet = (derivedStatus && derivedStatus.summary_not_generated_yet) || false;
  const topicsNotGeneratedYet = (derivedStatus && derivedStatus.topics_not_generated_yet) || false;
  const agendaNotGeneratedYet = (derivedStatus && derivedStatus.agenda_not_generated_yet) || false;
  const effectiveSummaryBlockReason = (derivedStatus && derivedStatus.summary_blocked_reason) || summaryBlockReason;
  const effectiveTopicsBlockReason = (derivedStatus && derivedStatus.topics_blocked_reason) || topicsBlockReason;
  const handleTopicClick = (topic) => {
    // Topics are meant to be a quick way to narrow the search.
    // We keep this simple: clicking a topic sets the main search query
    // (handled in the parent page).
    if (onTopicClick) onTopicClick(topic);
  };

  const handleReportIssue = async (issueType) => {
    if (!canMutate) return;
    setReportStatus('loading');
    try {
      const res = await fetch(`${API_BASE_URL}/report-issue`, {
        method: "POST",
        headers: getApiHeaders({ useAuth: true, json: true }),
        body: JSON.stringify({
          event_id: hit.event_id || hit.id,
          issue_type: issueType,
          description: "Reported from web UI"
        })
      });
      if (res.ok) {
        setReportStatus('success');
        // Hide the form after 3 seconds of success
        setTimeout(() => {
          setIsReporting(false);
          setReportStatus(null);
        }, 3000);
      } else {
        setReportStatus('error');
      }
    } catch (err) {
      console.error("Reporting failed", err);
      setReportStatus('error');
    }
  };

  // Fetch related meetings when expanded
  useEffect(() => {
    if (isExpanded && hit.related_ids && hit.related_ids.length > 0 && !relatedMeetings) {
      fetchRelatedMeetings();
    }
  }, [isExpanded, hit.related_ids]);

  // Fetch derived staleness status (summary/topics) when expanded so the UI can
  // show "stale" badges after a re-extraction.
  useEffect(() => {
    if (!isExpanded || !hit.catalog_id) return;
    fetchDerivedStatus();
  }, [isExpanded, hit.catalog_id]);

  // Full Text should come from the DB, not from the search index.
  // Meilisearch results can be stale after startup purge or indexing changes.
  useEffect(() => {
    if (!isExpanded || !hit.catalog_id) return;
    fetchCanonicalContent();
  }, [isExpanded, hit.catalog_id]);

  const fetchDerivedStatus = async () => {
    if (!hit.catalog_id) return;
    try {
      const res = await fetch(buildApiUrl(`/catalog/${hit.catalog_id}/derived_status`), {
        headers: getApiHeaders({ useAuth: canMutate }),
      });
      if (!res.ok) return;
      const data = await res.json();
      setDerivedStatus(data);
    } catch (err) {
      // Best-effort only; staleness badges are helpful but not critical.
      console.error("Failed to fetch derived status", err);
    }
  };

  const fetchCanonicalContent = async () => {
    if (!hit.catalog_id) return;
    if (!demoMode && !canMutate) {
      // The API protects /catalog/* endpoints with an API key. Without a key we can still
      // browse search results, but we can't show canonical extracted text.
      setCanonicalTextFetchFailed(true);
      setCanonicalTextLoadError("Missing API key (cannot load canonical extracted text).");
      return;
    }

    setIsLoadingCanonicalText(true);
    setCanonicalTextLoadError(null);
    try {
      const res = await fetch(buildApiUrl(`/catalog/${hit.catalog_id}/content`), {
        headers: getApiHeaders({ useAuth: canMutate }),
      });
      if (!res.ok) {
        setCanonicalTextFetchFailed(true);
        setCanonicalTextLoadError(`Failed to load extracted text (HTTP ${res.status}).`);
        setIsLoadingCanonicalText(false);
        return;
      }

      const data = await res.json();
      setExtractedTextOverride(typeof data.content === "string" ? data.content : "");
      setCanonicalTextFetchFailed(false);
      setIsLoadingCanonicalText(false);
    } catch (err) {
      console.error("Failed to fetch canonical text", err);
      setCanonicalTextFetchFailed(true);
      setCanonicalTextLoadError("Failed to load extracted text (network error).");
      setIsLoadingCanonicalText(false);
    }
  };

  const fetchRelatedMeetings = async () => {
    setIsLoadingRelated(true);
    try {
      const params = new URLSearchParams();
      hit.related_ids.forEach(id => params.append('ids', id));
      
      const res = await fetch(buildApiUrl(`/catalog/batch?${params.toString()}`), {
        headers: getApiHeaders({ useAuth: canMutate })
      });
      const data = await res.json();
      setRelatedMeetings(data);
    } catch (err) {
      console.error("Failed to fetch related meetings", err);
    } finally {
      setIsLoadingRelated(false);
    }
  };

  const handleGenerateSummary = async ({ force = false } = {}) => {
    if (!hit.catalog_id || demoMode) return;
    
    setIsGenerating(true);
    try {
      const url = new URL(`${API_BASE_URL}/summarize/${hit.catalog_id}`);
      if (force) url.searchParams.set("force", "true");

      const res = await fetch(url.toString(), {
        method: "POST",
        headers: getApiHeaders({ useAuth: true })
      });
      const data = await res.json();
      
      if ((data.status === 'cached' || data.status === 'stale') && data.summary) {
        setSummary(data.summary);
        setSummaryBlockReason(null);
        setIsGenerating(false);
        fetchDerivedStatus();
      } else if (data.status === "blocked_low_signal" || data.status === "blocked_ungrounded") {
        setSummary(null);
        setSummaryBlockReason(data.reason || "Not enough extracted text to generate a reliable summary.");
        setIsGenerating(false);
        fetchDerivedStatus();
      } else if (data.task_id) {
        pollTaskStatus(data.task_id, (result) => {
          if (result && (result.status === "blocked_low_signal" || result.status === "blocked_ungrounded")) {
            setSummary(null);
            setSummaryBlockReason(result.reason || "Not enough extracted text to generate a reliable summary.");
          } else {
            setSummary((result && result.summary) || null);
            setSummaryBlockReason(null);
          }
          setIsGenerating(false);
          fetchDerivedStatus();
        }, () => setIsGenerating(false), 'summary');
      } else {
        setIsGenerating(false);
      }
    } catch (err) {
      console.error("AI Generation failed", err);
      setIsGenerating(false);
    }
  };

  const handleGenerateTopics = async ({ force = false } = {}) => {
    if (!hit.catalog_id || demoMode) return;
    setIsTaggingTopics(true);
    try {
      const url = new URL(`${API_BASE_URL}/topics/${hit.catalog_id}`);
      if (force) url.searchParams.set("force", "true");

      const res = await fetch(url.toString(), {
        method: "POST",
        headers: getApiHeaders({ useAuth: true }),
      });
      const data = await res.json();

      if ((data.status === "cached" || data.status === "stale") && data.topics) {
        setTopics(data.topics || []);
        setTopicsBlockReason(null);
        setIsTaggingTopics(false);
        fetchDerivedStatus();
      } else if (data.status === "blocked_low_signal") {
        setTopics([]);
        setTopicsBlockReason(data.reason || "Not enough extracted text to generate reliable topics.");
        setIsTaggingTopics(false);
        fetchDerivedStatus();
      } else if (data.task_id) {
        pollTaskStatus(
          data.task_id,
          (result) => {
            if (result && result.status === "blocked_low_signal") {
              setTopics([]);
              setTopicsBlockReason(result.reason || "Not enough extracted text to generate reliable topics.");
            } else {
              setTopics((result && result.topics) || []);
              setTopicsBlockReason(null);
            }
            setIsTaggingTopics(false);
            fetchDerivedStatus();
          },
          () => setIsTaggingTopics(false),
          "topics"
        );
      } else {
        setIsTaggingTopics(false);
      }
    } catch (err) {
      console.error("Topic generation failed", err);
      setIsTaggingTopics(false);
    }
  };

  const handleGenerateAgenda = async ({ force = false } = {}) => {
    if (!hit.catalog_id || demoMode) return;
    
    setIsSegmenting(true);
    try {
      const url = new URL(`${API_BASE_URL}/segment/${hit.catalog_id}`);
      if (force) url.searchParams.set("force", "true");

      const res = await fetch(url.toString(), {
        method: "POST",
        headers: getApiHeaders({ useAuth: true })
      });
      const data = await res.json();
      
      if (data.status === 'cached' && data.items) {
        setAgendaItems(data.items);
        setIsSegmenting(false);
        // Refresh derived status so "Not generated yet" clears immediately after segmentation.
        fetchDerivedStatus();
      } else if (data.task_id) {
        pollTaskStatus(data.task_id, (result) => {
          setAgendaItems(result);
          setIsSegmenting(false);
          // Segmentation creates AgendaItem rows; update derived status so badges stay in sync.
          fetchDerivedStatus();
        }, () => setIsSegmenting(false), 'agenda');
      } else {
        setIsSegmenting(false);
      }
    } catch (err) {
      console.error("Agenda segmentation failed", err);
      setIsSegmenting(false);
    }
  };

  const handleReextractText = async ({ ocrFallback = true } = {}) => {
    if (!hit.catalog_id || demoMode) return;
    setIsExtracting(true);
    try {
      const url = new URL(`${API_BASE_URL}/extract/${hit.catalog_id}`);
      url.searchParams.set("force", "true");
      if (ocrFallback) url.searchParams.set("ocr_fallback", "true");

      const res = await fetch(url.toString(), {
        method: "POST",
        headers: getApiHeaders({ useAuth: true }),
      });
      const data = await res.json();
      if (data.status === "cached") {
        // Pull fresh text from the DB endpoint even when cached so the UI refreshes.
        await fetchCanonicalContent();
        setIsExtracting(false);
        fetchDerivedStatus();
        return;
      }

      if (data.task_id) {
        pollTaskStatus(
          data.task_id,
          async () => {
            await fetchCanonicalContent();
            setIsExtracting(false);
            fetchDerivedStatus();
          },
          () => setIsExtracting(false),
          "extract"
        );
        return;
      }

      setIsExtracting(false);
    } catch (err) {
      console.error("Re-extraction failed", err);
      setIsExtracting(false);
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
            <button 
              onClick={() => setIsReporting(!isReporting)}
              disabled={!canMutate}
              className={`p-2.5 rounded-xl transition-all border disabled:opacity-40 disabled:cursor-not-allowed ${isReporting ? 'bg-red-50 text-red-600 border-red-200' : 'bg-gray-50 text-gray-400 hover:bg-red-50 hover:text-red-600 border-transparent hover:border-red-100'}`}
              title={canMutate ? "Report Data Error" : "Unavailable in static demo mode"}
            >
              <Flag className="w-5 h-5" />
            </button>
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

        {isReporting && (
          <div className="mb-6 p-4 bg-red-50/50 border border-red-100 rounded-2xl animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-red-700 font-bold text-[11px] uppercase tracking-widest">
                <AlertCircle className="w-4 h-4" />
                Report Data Issue
              </div>
              <button onClick={() => setIsReporting(false)} className="text-gray-400 hover:text-gray-600 text-xs font-medium">Cancel</button>
            </div>
            
            {reportStatus === 'success' ? (
              <div className="py-4 flex flex-col items-center gap-2 text-center">
                <div className="bg-green-100 p-2 rounded-full">
                  <CheckCircle className="w-6 h-6 text-green-600" />
                </div>
                <p className="text-sm font-bold text-green-800">Thank you! Report received.</p>
                <p className="text-[11px] text-green-600">Our team will review this meeting.</p>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-xs text-red-600/70 mb-3">What seems to be the problem with this data?</p>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { id: 'broken_link', label: 'Broken Link' },
                    { id: 'garbled_text', label: 'Garbled Text' },
                    { id: 'wrong_city', label: 'Wrong City' },
                    { id: 'other', label: 'Other Issue' }
                  ].map((type) => (
                    <button
                      key={type.id}
                      disabled={reportStatus === 'loading'}
                      onClick={() => handleReportIssue(type.id)}
                      className="px-3 py-2 bg-white border border-red-100 text-[11px] font-bold text-gray-700 rounded-xl hover:bg-red-600 hover:text-white hover:border-red-600 transition-all text-left flex items-center justify-between group"
                    >
                      {type.label}
                      {reportStatus === 'loading' ? <Loader2 className="w-3 h-3 animate-spin" /> : <ChevronDown className="w-3 h-3 -rotate-90 opacity-0 group-hover:opacity-100" />}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {hit.people_metadata && hit.people_metadata.length > 0 && (
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mr-1">Officials:</span>
            {(showAllOfficials ? hit.people_metadata : hit.people_metadata.slice(0, 5)).map((person) => (
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
              <button 
                onClick={() => setShowAllOfficials(!showAllOfficials)}
                className="text-[10px] text-blue-600 font-bold hover:underline transition-all"
              >
                {showAllOfficials ? "Show Less" : `+${hit.people_metadata.length - 5} more`}
              </button>
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
                {!isAgendaItem && (
                  <button 
                    onClick={() => setViewMode("agenda")}
                    className={`px-4 py-2 text-xs font-bold rounded-lg transition-all flex items-center gap-2 whitespace-nowrap ${viewMode === "agenda" ? 'bg-indigo-600 text-white shadow-sm' : 'text-gray-500 hover:bg-gray-50'}`}
                  >
                    <TableIcon className={`w-3.5 h-3.5 ${viewMode === "agenda" ? 'text-white' : 'text-indigo-500'}`} />
                    Structured Agenda
                  </button>
                )}
                <button 
                  onClick={() => setViewMode("summary")}
                  className={`px-4 py-2 text-xs font-bold rounded-lg transition-all flex items-center gap-2 whitespace-nowrap ${viewMode === "summary" ? 'bg-purple-600 text-white shadow-sm' : 'text-gray-500 hover:bg-gray-50'}`}
                >
                  <Sparkles className={`w-3.5 h-3.5 ${viewMode === "summary" ? 'text-white' : 'text-purple-500'}`} />
                  AI Summary
                </button>
              </div>
	              <span className="hidden sm:block px-4 text-[10px] font-bold text-gray-400 uppercase tracking-widest">
	                {demoMode ? "Demo Mode" : (viewMode === "text" ? "Extracted Text" : "Local AI")}
	              </span>
            </div>

            <div className="relative">
              {demoMode && (
                <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2">
                  <p className="text-[12px] text-amber-800">
                    Demo mode uses static fixtures. AI generation, segmentation, topic tagging, and re-extraction are disabled.
                  </p>
                </div>
              )}
              {viewMode === "summary" ? (
                <div className="p-8 bg-purple-50/30 border border-purple-100 rounded-3xl space-y-6">
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-purple-700 font-bold text-[11px] uppercase tracking-widest">
                        <Sparkles className="w-4 h-4" />
                        Executive Summary
                      </div>
		                    {summary ? (
		                        <div className="space-y-4">
		                        <div className="flex items-center gap-2">
		                          <span className="bg-purple-100 text-purple-700 text-[9px] font-black uppercase px-1.5 py-0.5 rounded shadow-sm">Gemma 3 270M</span>
		                          {summaryIsStale && (
		                            <span className="bg-amber-100 text-amber-800 text-[9px] font-black uppercase px-1.5 py-0.5 rounded shadow-sm" title="The extracted text changed after this summary was generated.">
		                              Stale
		                            </span>
		                          )}
                              {summaryNotGeneratedYet && !summaryIsStale && !effectiveSummaryBlockReason && (
                                <span className="bg-slate-100 text-slate-700 text-[9px] font-black uppercase px-1.5 py-0.5 rounded shadow-sm">
                                  Not generated yet
                                </span>
                              )}
		                        </div>
		                        <p className="text-gray-800 text-[15px] whitespace-pre-line leading-relaxed italic">
		                          {summary}
		                        </p>
	                        <button
	                          type="button"
	                          onClick={() => handleGenerateSummary({ force: true })}
	                          disabled={!canMutate || isGenerating}
	                          className="text-[10px] font-bold text-purple-600 hover:text-purple-800 flex items-center gap-1 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
	                          title={canMutate ? "Regenerate the cached summary (useful after summarization logic changes)" : "Unavailable in static demo mode"}
	                        >
	                          <Sparkles className="w-3 h-3" /> Regenerate summary
	                        </button>
	                      </div>
                    ) : effectiveSummaryBlockReason ? (
                      <div className="space-y-4">
                        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                          <p className="text-[12px] font-bold text-amber-800 uppercase tracking-wide">Summary blocked</p>
                          <p className="text-[13px] text-amber-700 mt-1">{effectiveSummaryBlockReason}</p>
                        </div>
                        <div className="flex gap-3 items-center">
                          {canMutate && hit.catalog_id && (
                            <button
                              type="button"
                              onClick={() => handleReextractText({ ocrFallback: true })}
                              disabled={isExtracting}
                              className="text-[10px] font-bold text-blue-600 hover:text-blue-800 underline underline-offset-4 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {isExtracting ? "Re-extracting..." : "Re-extract text"}
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => handleGenerateSummary({ force: true })}
                            disabled={!canMutate || isGenerating}
                            className="text-[10px] font-bold text-purple-600 hover:text-purple-800 flex items-center gap-1 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <Sparkles className="w-3 h-3" /> Retry summary
                          </button>
                        </div>
                      </div>
                    ) : hit.summary_extractive ? (
                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <span className="bg-indigo-100 text-indigo-700 text-[9px] font-black uppercase px-1.5 py-0.5 rounded shadow-sm">Local Fast-Pass AI</span>
	                          <button 
	                            onClick={() => handleGenerateSummary()}
	                            disabled={!canMutate || isGenerating}
	                            className="text-[10px] font-bold text-purple-600 hover:text-purple-800 flex items-center gap-1 transition-colors"
	                          >
	                            <Sparkles className="w-3 h-3" /> Upgrade to Local Generative AI
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
                        <h4 className="font-bold text-purple-900 mb-1">
                          {summaryNotGeneratedYet ? "Not generated yet" : "No summary yet"}
                        </h4>
                        <p className="text-purple-600/60 text-xs mb-6 max-w-[240px] text-center">
                          Generate an executive summary using local AI.
                        </p>
	                        <button 
	                          onClick={() => handleGenerateSummary()}
	                          disabled={!canMutate || isGenerating}
	                          className="px-6 py-2.5 bg-purple-600 text-white text-xs font-bold rounded-xl shadow-lg shadow-purple-200 hover:bg-purple-700 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
	                        >
                          {isGenerating ? (
                            <><Loader2 className="w-4 h-4 animate-spin" /> Reading...</>
                          ) : (
                            <><Sparkles className="w-3.5 h-3.5" /> Generate Local Summary</>
                          )}
                        </button>
                      </div>
                    )}
                  </div>

                  {(hit.entities || (topics && topics.length > 0) || effectiveTopicsBlockReason || topicsNotGeneratedYet) && (
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
		                      {(topics && topics.length > 0) || effectiveTopicsBlockReason || topicsNotGeneratedYet ? (
		                        <div className="space-y-3">
		                          <div className="flex items-center justify-between">
		                            <div className="flex items-center gap-2">
		                              <div className="text-[10px] font-bold text-purple-400 uppercase tracking-widest">Discovered Topics</div>
		                              {topicsIsStale && (
		                                <span className="bg-amber-100 text-amber-800 text-[9px] font-black uppercase px-1.5 py-0.5 rounded shadow-sm" title="The extracted text changed after these topics were generated.">
		                                  Stale
		                                </span>
		                              )}
                                  {topicsNotGeneratedYet && !topicsIsStale && !effectiveTopicsBlockReason && (
                                    <span className="bg-slate-100 text-slate-700 text-[9px] font-black uppercase px-1.5 py-0.5 rounded shadow-sm">
                                      Not generated yet
                                    </span>
                                  )}
		                            </div>
		                            {canMutate && hit.catalog_id && (
		                              <button
		                                type="button"
		                                onClick={() => handleGenerateTopics({ force: true })}
		                                disabled={isTaggingTopics}
		                                className="text-[10px] font-bold text-purple-600 hover:text-purple-800 flex items-center gap-1 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
		                                title="Regenerate topic tags for this catalog (explicit action; does not run automatically)."
		                              >
		                                <Sparkles className="w-3 h-3" /> Regenerate topics
		                              </button>
		                            )}
		                          </div>
                              {effectiveTopicsBlockReason ? (
                                <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2">
                                  <p className="text-[12px] text-amber-700">Topics unavailable: {effectiveTopicsBlockReason}</p>
                                </div>
                              ) : topicsNotGeneratedYet ? (
                                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                                  <p className="text-[12px] text-slate-700">Topics are not generated yet.</p>
                                </div>
                              ) : (
		                            <div className="flex flex-wrap gap-2">
		                              {(topics || []).map((topic, i) => (
		                                <button
		                                  key={i}
		                                  type="button"
		                                  onClick={() => handleTopicClick(topic)}
		                                  disabled={topicsIsStale}
		                                  className={`px-3 py-1.5 text-[11px] font-bold rounded-xl border uppercase tracking-tight transition-colors ${
		                                    topicsIsStale
		                                      ? "bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed"
		                                      : "bg-purple-100/50 text-purple-700 border-purple-200 hover:bg-purple-100 hover:border-purple-300"
		                                  }`}
		                                  title={topicsIsStale ? "Topics are stale; regenerate to use them for search." : "Search for this topic"}
		                                >
		                                  #{topic}
		                                </button>
		                              ))}
	                            </div>
                              )}
	                        </div>
	                      ) : null}
                    </div>
                  )}
                </div>
              ) : viewMode === "agenda" ? (
                <div className="p-8 bg-indigo-50/30 border border-indigo-100 rounded-3xl space-y-6">
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-indigo-700 font-bold text-[11px] uppercase tracking-widest">
                      <TableIcon className="w-4 h-4" />
                      Segmented Agenda Items
                      {agendaNotGeneratedYet && (
                        <span className="bg-slate-100 text-slate-700 text-[9px] font-black uppercase px-1.5 py-0.5 rounded shadow-sm">
                          Not generated yet
                        </span>
                      )}
                    </div>
                    {agendaItems && agendaItems.length > 0 ? (
                      <div className="grid gap-4">
                        {agendaItems.map((item, i) => (
                          <div key={i} className="p-4 bg-white border border-indigo-100 rounded-2xl shadow-sm hover:border-indigo-300 transition-colors group/item">
                            <div className="flex items-start gap-3">
                              <span className="bg-indigo-100 text-indigo-700 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0">{item.order || i+1}</span>
                              <div className="flex-1 space-y-1">
                                <div className="flex justify-between items-start">
                                  <h5 className="font-bold text-gray-900 text-sm leading-tight">{item.title}</h5>
                                  {item.page_number && (
                                    <a 
                                      href={`${hit.url}#page=${item.page_number}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-[10px] font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded flex items-center gap-1 hover:bg-indigo-600 hover:text-white transition-all shadow-sm"
                                    >
                                      <FileText className="w-2.5 h-2.5" /> Page {item.page_number}
                                    </a>
                                  )}
                                </div>
                                <p className="text-xs text-gray-600 leading-relaxed">{item.description}</p>
                                {item.result && (
                                  <p className="text-xs text-emerald-700 font-semibold">Vote: {item.result}</p>
                                )}
                                {item.votes && Array.isArray(item.votes) && item.votes.length > 0 && (
                                  <p className="text-xs text-emerald-700 font-semibold">
                                    Votes: {item.votes.map((v) => `${v.member || "Member"} ${v.vote || ""}`.trim()).join(", ")}
                                  </p>
                                )}
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
                        <h4 className="font-bold text-indigo-900 mb-1">
                          {agendaNotGeneratedYet
                            ? "Not generated yet"
                            : (agendaItems && agendaItems.length === 0 ? "No items found" : "Agenda not segmented")}
                        </h4>
                        <p className="text-indigo-600/60 text-xs mb-6 max-w-[240px] text-center">
                          {agendaItems && agendaItems.length === 0 
                            ? "The AI was unable to find specific agenda items in this document." 
                            : "Use AI to split this document into individual, searchable agenda items."}
                        </p>
                        <button 
                          onClick={handleGenerateAgenda}
                          disabled={!canMutate || isSegmenting}
                          className="px-6 py-2.5 bg-indigo-600 text-white text-xs font-bold rounded-xl shadow-lg shadow-indigo-200 hover:bg-indigo-700 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                          {isSegmenting ? (
                            <><Loader2 className="w-4 h-4 animate-spin" /> Splitting...</>
                          ) : (
                            <><Sparkles className="w-3.5 h-3.5" /> {agendaItems && agendaItems.length === 0 ? "Retry Segmentation" : "Segment Agenda Items"}</>
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
	                      Extracted Text
                        {(derivedStatus && derivedStatus.has_content === false) && (
                          <span className="bg-slate-100 text-slate-700 text-[9px] font-black uppercase px-1.5 py-0.5 rounded shadow-sm">
                            Not extracted yet
                          </span>
                        )}
	                    </div>
                      {canonicalTextLoadError && (
                        <div className="mb-4 text-[12px] text-amber-800 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                          {canonicalTextLoadError}{" "}
                          {canonicalTextFetchFailed && typeof hit.content === "string" && hit.content.length > 0
                            ? "Showing search snippet instead."
                            : null}
                        </div>
                      )}
                      {isLoadingCanonicalText && (
                        <div className="mb-4 text-[12px] text-gray-500">Loading extracted text...</div>
                      )}
	                    {canMutate && hit.catalog_id && (
	                      <button
	                        type="button"
	                        onClick={() => handleReextractText({ ocrFallback: true })}
	                        disabled={isExtracting}
	                        className="mb-4 text-[11px] font-bold text-blue-600 hover:text-blue-800 underline underline-offset-4 disabled:opacity-50 disabled:cursor-not-allowed"
	                        title="Re-extract text from the already-downloaded PDF file (no re-download). OCR fallback may be slower."
	                      >
	                        {isExtracting ? "Re-extracting..." : "Re-extract text"}
	                      </button>
	                    )}
                      {typeof extractedTextOverride === "string" ? (
                        extractedTextOverride.trim() === "" ? (
                          <p className="text-[13px] text-gray-500 italic">
                            Not extracted yet. Use <span className="font-semibold">Re-extract text</span> to load the canonical document text.
                          </p>
                        ) : (
                          <div
                            className="leading-relaxed text-[14px]"
                            dangerouslySetInnerHTML={{
                              __html: DOMPurify.sanitize(formattedFullTextHtml)
                            }}
                          />
                        )
                      ) : formattedFullTextHtml ? (
	                      <div
	                        className="leading-relaxed text-[14px]"
	                        dangerouslySetInnerHTML={{
	                          __html: DOMPurify.sanitize(formattedFullTextHtml)
	                        }}
	                      />
	                    ) : hit._formatted && hit._formatted.content ? (
	                      <div 
	                        className="whitespace-pre-line leading-relaxed text-[14px]"
	                        dangerouslySetInnerHTML={{
	                          __html: DOMPurify.sanitize(hit._formatted.content)
	                        }}
	                      />
	                    ) : canonicalTextFetchFailed ? (
	                      <p className="whitespace-pre-line leading-relaxed text-[14px]">{hit.content}</p>
	                    ) : (
                        <p className="text-[13px] text-gray-500 italic">
                          Not extracted yet. Use <span className="font-semibold">Re-extract text</span> to load the canonical document text.
                        </p>
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

            {hit.related_ids && hit.related_ids.length > 0 && (
              <div className="space-y-4 pt-6 border-t border-gray-100">
                <div className="flex items-center gap-2 text-gray-400 font-bold text-[10px] uppercase tracking-widest">
                  <Link2 className="w-4 h-4" />
                  Related Discussions
                </div>
                {isLoadingRelated ? (
                  <div className="flex items-center gap-2 text-xs text-gray-400 italic">
                    <Loader2 className="w-3 h-3 animate-spin" /> Finding similar meetings...
                  </div>
                ) : relatedMeetings && (
                  <div className="grid gap-3">
                    {relatedMeetings.map((related) => (
                      <div key={related.id} className="flex items-center justify-between p-3 bg-gray-50/50 hover:bg-blue-50/50 rounded-xl border border-gray-100 transition-colors group/rel">
                        <div className="flex flex-col gap-0.5">
                          <span className="text-[13px] font-bold text-gray-800 group-hover/rel:text-blue-700 transition-colors">{related.title}</span>
                          <span className="text-[11px] text-gray-500 font-medium">{related.city} • {new Date(related.date).toLocaleDateString(undefined, { dateStyle: 'medium' })}</span>
                        </div>
                        <button className="text-[10px] font-black uppercase text-blue-600 opacity-0 group-hover/rel:opacity-100 transition-opacity flex items-center gap-1">
                          View <ChevronDown className="w-3 h-3 -rotate-90" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
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
