"use client";

import { useState, useRef, useEffect } from "react";

export interface TickerSuggestion {
  ticker: string;
  name: string;
  exchange: string;
  exchange_name?: string;
  type: string;
  sector?: string;
  industry?: string;
}

interface UseTickerSearchReturn {
  ticker: string;
  suggestions: TickerSuggestion[];
  showSuggestions: boolean;
  selectedIdx: number;
  inputRef: React.RefObject<HTMLInputElement>;
  dropdownRef: React.RefObject<HTMLDivElement>;
  handleTickerChange: (value: string) => void;
  handleKeyDown: (e: React.KeyboardEvent) => void;
  selectSuggestion: (t: string) => void;
}

export function useTickerSearch(onSelect?: (ticker: string) => void): UseTickerSearchReturn {
  const [ticker, _setTicker] = useState("");
  const [suggestions, setSuggestions] = useState<TickerSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(-1);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const skipNextRef = useRef(false);   // selectSuggestion sonrasi fetch'i atla

  // outside click handler
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current && !inputRef.current.contains(e.target as Node)
      ) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // debounced fetch
  useEffect(() => {
    if (ticker.length < 1) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    if (skipNextRef.current) {
      skipNextRef.current = false;
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/api/screener/suggest?q=${encodeURIComponent(ticker)}`,
          { cache: "no-store" }
        );
        if (res.ok) {
          const data = await res.json();
          setSuggestions(data.slice(0, 8));
          setShowSuggestions(data.length > 0);
          setSelectedIdx(-1);
        }
      } catch (e) { console.warn("Failed to fetch suggestions", e); }
    }, 200);
    return () => clearTimeout(timer);
  }, [ticker]);

  const handleTickerChange = (value: string) => {
    _setTicker(value.toUpperCase());
  };

  const selectSuggestion = (t: string) => {
    skipNextRef.current = true;   // sonraki fetch'i engelle
    _setTicker(t);
    setShowSuggestions(false);
    setSuggestions([]);
    onSelect?.(t);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showSuggestions) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIdx((prev) => Math.min(prev + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIdx((prev) => Math.max(prev - 1, -1));
    } else if (e.key === "Enter" && selectedIdx >= 0) {
      e.preventDefault();
      const s = suggestions[selectedIdx];
      if (s) selectSuggestion(s.ticker);
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
    }
  };

  return {
    ticker,
    suggestions,
    showSuggestions,
    selectedIdx,
    inputRef,
    dropdownRef,
    handleTickerChange,
    handleKeyDown,
    selectSuggestion,
  };
}
