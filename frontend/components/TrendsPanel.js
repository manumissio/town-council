import { useEffect, useState } from "react";
import { BarChart3, Loader2 } from "lucide-react";
import { buildApiUrl, getApiHeaders } from "../lib/api";

// NOTE:
// This component is intentionally not mounted in page.js right now.
// Why: early user testing showed Topic Momentum competes with the core search
// flow and creates uncertainty about the first action. We keep the component in
// place so Milestone C can be resumed quickly without reimplementation.
export default function TrendsPanel({ enabled, onTopicClick }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const res = await fetch(buildApiUrl("/trends/topics?limit=8"), {
          headers: getApiHeaders({ useAuth: true }),
        });
        if (!res.ok) {
          if (active) setError(`Unable to load trends (HTTP ${res.status}).`);
          return;
        }
        const data = await res.json();
        if (active) setRows(Array.isArray(data.items) ? data.items : []);
      } catch (_err) {
        if (active) setError("Unable to load trends.");
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [enabled]);

  if (!enabled) return null;

  return (
    <section className="max-w-6xl mx-auto px-4 pt-6">
      <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2 text-slate-700 font-bold text-[11px] uppercase tracking-widest mb-3">
          <BarChart3 className="w-4 h-4" />
          Topic Momentum
        </div>
        {loading ? (
          <div className="text-sm text-slate-500 flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading trends...
          </div>
        ) : error ? (
          <div className="text-sm text-slate-500">{error}</div>
        ) : rows.length === 0 ? (
          <div className="text-sm text-slate-500">No trend data available for the selected window.</div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {rows.map((row) => (
              <button
                key={row.topic}
                type="button"
                onClick={() => onTopicClick && onTopicClick(row.topic)}
                className="rounded-xl border border-slate-100 bg-slate-50 p-3 text-left hover:border-blue-300 hover:bg-blue-50 transition-colors"
                title="Search this topic"
              >
                <p className="text-xs uppercase tracking-wide text-slate-500">{row.topic}</p>
                <p className="text-lg font-bold text-slate-800">{row.count}</p>
              </button>
            ))}
          </div>
        )}
        <p className="mt-3 text-xs text-slate-500">Click a topic to run a search.</p>
      </div>
    </section>
  );
}
