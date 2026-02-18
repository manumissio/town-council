"use client";

import { createContext, useContext, useMemo, useState } from "react";

const SearchStateContext = createContext(null);

export function SearchStateProvider({ children }) {
  const [query, setQuery] = useState("");
  const [cityFilter, setCityFilter] = useState("");
  const [meetingTypeFilter, setMeetingTypeFilter] = useState("");
  const [orgFilter, setOrgFilter] = useState("");
  const [includeAgendaItems, setIncludeAgendaItems] = useState(false);
  const [searchMode, setSearchMode] = useState("keyword");
  const [sortMode, setSortMode] = useState("newest");

  const value = useMemo(
    () => ({
      query,
      setQuery,
      cityFilter,
      setCityFilter,
      meetingTypeFilter,
      setMeetingTypeFilter,
      orgFilter,
      setOrgFilter,
      includeAgendaItems,
      setIncludeAgendaItems,
      searchMode,
      setSearchMode,
      sortMode,
      setSortMode,
    }),
    [
      query,
      cityFilter,
      meetingTypeFilter,
      orgFilter,
      includeAgendaItems,
      searchMode,
      sortMode,
    ]
  );

  return <SearchStateContext.Provider value={value}>{children}</SearchStateContext.Provider>;
}

export function useSearchState() {
  const ctx = useContext(SearchStateContext);
  if (!ctx) {
    throw new Error("useSearchState must be used inside SearchStateProvider");
  }
  return ctx;
}

