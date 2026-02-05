"use client";

import { useState, useEffect } from "react";
import DOMPurify from "isomorphic-dompurify";
import { Search, FileText, Calendar, MapPin, Sparkles, Building2, Tag, Table as TableIcon, Layout } from "lucide-react";

/**
 * Renders a structured JSON table as an HTML table.
 */
function DataTable({ data }) {
  if (!data || data.length === 0) return null;
  
  // Use first row as header if it exists
  const headers = data[0];
  const rows = data.slice(1, 6); // Only show first 5 rows for performance

  return (
    <div className="mt-4 overflow-x-auto border border-gray-200 rounded-lg">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {headers.map((cell, i) => (
              <th key={i} className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-2 whitespace-nowrap text-xs text-gray-700">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length > 6 && (
        <div className="px-4 py-1 text-center text-[10px] text-gray-400 bg-gray-50 italic">
          Showing 5 of {data.length} rows
        </div>
      )}
    </div>
  );
}

export default function Home() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);

  // Debounce search requests to avoid overloading the API
  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      if (query.trim()) {
        performSearch();
      } else {
        setResults([]);
      }
    }, 300); // Wait 300ms after user stops typing

    return () => clearTimeout(delayDebounceFn);
  }, [query]);

  // Fetch index stats on load
  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${apiUrl}/stats`)
      .then((res) => res.json())
      .then((data) => setStats(data))
      .catch((err) => console.error("Failed to fetch stats", err));
  }, []);

  const performSearch = async () => {
    setLoading(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/search?q=${encodeURIComponent(query)}`);
      const data = await res.json();
      // Meilisearch returns results in 'hits' array
      setResults(data.hits || []);
    } catch (error) {
      console.error("Search failed:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="max-w-4xl mx-auto p-6">
      {/* Header Section */}
      <div className="text-center mb-12 mt-10">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">Town Council Search</h1>
        <p className="text-lg text-gray-600">
          Instantly search meeting minutes across {stats?.numberOfDocuments || "multiple"} indexed documents.
        </p>
      </div>

      {/* Search Bar */}
      <div className="relative mb-10">
        <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
          <Search className="w-5 h-5 text-gray-400" />
        </div>
        <input
          type="search"
          className="block w-full p-4 pl-10 text-sm text-gray-900 border border-gray-300 rounded-lg bg-white focus:ring-blue-500 focus:border-blue-500 shadow-sm"
          placeholder="Search for 'zoning', 'police budget', 'housing'..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {loading && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-3">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500"></div>
          </div>
        )}
      </div>

      {/* Results List */}
      <div className="space-y-4">
        {results.map((hit) => (
          <div key={hit.id} className="p-6 bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start mb-2">
              <h2 className="text-xl font-semibold text-blue-600">
                {hit.event_name || "Untitled Meeting"}
              </h2>
              <span className="bg-blue-100 text-blue-800 text-xs font-medium mr-2 px-2.5 py-0.5 rounded">
                {hit.city}
              </span>
            </div>

            <div className="flex items-center gap-4 text-sm text-gray-500 mb-4">
              <div className="flex items-center gap-1">
                <Calendar className="w-4 h-4" />
                {hit.date ? new Date(hit.date).toLocaleDateString() : "Unknown Date"}
              </div>
              <div className="flex items-center gap-1">
                <MapPin className="w-4 h-4" />
                {hit.state}
              </div>
              <div className="flex items-center gap-1">
                <FileText className="w-4 h-4" />
                {hit.filename}
              </div>
            </div>

            {/* 
              AI SUMMARY SECTION
              Display the Gemini-generated summary if available.
            */}
            {hit.summary && (
              <div className="mb-4 p-3 bg-purple-50 border border-purple-100 rounded-md">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2 text-purple-700 font-medium text-xs uppercase tracking-wide">
                    <Sparkles className="w-3 h-3" />
                    AI Summary
                  </div>
                  {/* Render Topics if available */}
                  {hit.topics && (
                    <div className="flex gap-1">
                      {hit.topics.map((topic, i) => (
                        <span key={i} className="px-1.5 py-0.5 bg-purple-100 text-purple-600 text-[10px] font-bold rounded-full uppercase">
                          {topic}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <p className="text-gray-800 text-sm whitespace-pre-line">{hit.summary}</p>
              </div>
            )}

            {/* 
              NLP ENTITIES SECTION
              Display top organizations and locations mentioned in the document.
            */}
            {hit.entities && (
              <div className="mb-3 flex flex-wrap gap-2">
                {/* Organizations */}
                {(hit.entities.orgs || []).slice(0, 3).map((org, i) => (
                  <span key={`org-${i}`} className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-md border border-gray-200">
                    <Building2 className="w-3 h-3" />
                    {org}
                  </span>
                ))}
                {/* Locations */}
                {(hit.entities.locs || []).slice(0, 3).map((loc, i) => (
                  <span key={`loc-${i}`} className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-md border border-gray-200">
                    <MapPin className="w-3 h-3" />
                    {loc}
                  </span>
                ))}
                {/* overflow indicator */}
                {((hit.entities.orgs?.length || 0) + (hit.entities.locs?.length || 0)) > 6 && (
                  <span className="inline-flex items-center gap-1 px-2 py-1 text-gray-400 text-xs">
                    + more
                  </span>
                )}
              </div>
            )}

            {/* 
              SECURITY: Display search highlights safely.
              DOMPurify sanitizes the HTML to prevent XSS attacks from malicious indexed content.
            */}
            {hit._formatted && hit._formatted.content ? (
              <p 
                className="text-gray-600 text-sm leading-relaxed"
                dangerouslySetInnerHTML={{
                  __html: DOMPurify.sanitize(hit._formatted.content)
                }}
              />
            ) : (
              <p className="text-gray-600 text-sm line-clamp-3">{hit.content}</p>
            )}

            {/* 
              TABLES SECTION
              Render high-confidence tables if they were extracted from the PDF.
            */}
            {hit.tables && hit.tables.length > 0 && (
              <div className="mt-6">
                <div className="flex items-center gap-2 mb-2 text-gray-500 font-medium text-xs uppercase tracking-wide">
                  <TableIcon className="w-3 h-3" />
                  Extracted Tables ({hit.tables.length})
                </div>
                {hit.tables.slice(0, 2).map((table, i) => (
                  <DataTable key={i} data={table} />
                ))}
              </div>
            )}
            
            <div className="mt-4 pt-4 border-t border-gray-100">
              <a 
                href={hit.url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-sm text-blue-600 hover:underline"
              >
                View Original PDF &rarr;
              </a>
            </div>
          </div>
        ))}

        {query && !loading && results.length === 0 && (
          <div className="text-center text-gray-500 py-10">
            No results found for "{query}".
          </div>
        )}
      </div>
    </main>
  );
}
