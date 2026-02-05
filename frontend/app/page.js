"use client";

import { useState, useEffect } from "react";
import DOMPurify from "isomorphic-dompurify";
import { Search, FileText, Calendar, MapPin, Sparkles } from "lucide-react";

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
                <div className="flex items-center gap-2 mb-1 text-purple-700 font-medium text-xs uppercase tracking-wide">
                  <Sparkles className="w-3 h-3" />
                  AI Summary
                </div>
                <p className="text-gray-800 text-sm whitespace-pre-line">{hit.summary}</p>
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
