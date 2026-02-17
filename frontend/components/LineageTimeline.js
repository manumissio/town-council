import { useEffect, useState } from "react";
import { GitBranch, Loader2 } from "lucide-react";
import { buildApiUrl, getApiHeaders, isDemoMode } from "../lib/api";

export default function LineageTimeline({ catalogId, enabled }) {
  const [loading, setLoading] = useState(false);
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const demoMode = isDemoMode();

  useEffect(() => {
    if (!enabled || !catalogId || demoMode) return;
    let active = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const res = await fetch(buildApiUrl(`/catalog/${catalogId}/lineage`), {
          headers: getApiHeaders({ useAuth: true }),
        });
        if (!res.ok) {
          if (active) setError(`Unable to load lineage (HTTP ${res.status}).`);
          return;
        }
        const data = await res.json();
        if (active) setPayload(data);
      } catch (_err) {
        if (active) setError("Unable to load lineage.");
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [catalogId, enabled, demoMode]);

  if (!enabled || !catalogId) return null;
  if (demoMode) return null;
  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading issue timeline...
      </div>
    );
  }
  if (error) {
    return <div className="text-xs text-gray-500">{error}</div>;
  }
  if (!payload || !payload.lineage_id || !Array.isArray(payload.meetings) || payload.meetings.length <= 1) {
    return null;
  }

  return (
    <div className="space-y-3 pt-6 border-t border-gray-100">
      <div className="flex items-center gap-2 text-gray-400 font-bold text-[10px] uppercase tracking-widest">
        <GitBranch className="w-4 h-4" />
        Issue Timeline
      </div>
      <div className="grid gap-2">
        {payload.meetings.slice(0, 8).map((meeting) => (
          <div key={meeting.catalog_id} className="p-3 bg-gray-50 border border-gray-100 rounded-xl">
            <p className="text-sm font-semibold text-gray-800">{meeting.event_name || "Untitled Meeting"}</p>
            <p className="text-xs text-gray-500">
              {(meeting.city || "Unknown City")} • {meeting.date || "Unknown Date"} • confidence {(meeting.lineage_confidence || 0).toFixed(2)}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
