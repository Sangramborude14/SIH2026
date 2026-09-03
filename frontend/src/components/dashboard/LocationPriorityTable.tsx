"use client";

import React, { useState, useMemo } from "react";
import { LocationMapItem } from "./types";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  ExternalLink,
  ChevronUp,
  ChevronDown,
  Filter,
  Eye,
  SlidersHorizontal,
  Sparkles,
  ShieldAlert,
  Clock,
} from "lucide-react";

interface LocationPriorityTableProps {
  locations: LocationMapItem[];
  selectedLocationId: string | null;
  onSelectLocation: (locationId: string) => void;
  onOpenInvestigate: (locationId: string) => void;
}

type SortField =
  | "forecast_24h"
  | "risk_score"
  | "anomaly"
  | "trend"
  | "name"
  | "rainfall";
type SortOrder = "asc" | "desc";

export default function LocationPriorityTable({
  locations,
  selectedLocationId,
  onSelectLocation,
  onOpenInvestigate,
}: LocationPriorityTableProps) {
  const [filterLevel, setFilterLevel] = useState<string>("ALL");
  const [filterTrend, setFilterTrend] = useState<string>("ALL");
  const [sortField, setSortField] = useState<SortField>("forecast_24h");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
  };

  const filteredAndSortedLocations = useMemo(() => {
    return locations
      .filter((loc) => {
        if (filterLevel !== "ALL" && loc.risk_level?.toUpperCase() !== filterLevel) {
          return false;
        }
        const locTrend = (loc.trajectory || loc.trend_direction || "STABLE").toUpperCase();
        if (filterTrend !== "ALL" && locTrend !== filterTrend) {
          return false;
        }
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const matchesName = loc.name.toLowerCase().includes(q);
          const matchesDistrict = loc.district?.toLowerCase().includes(q);
          const matchesState = loc.state?.toLowerCase().includes(q);
          const matchesId = loc.id.toLowerCase().includes(q);
          if (!matchesName && !matchesDistrict && !matchesState && !matchesId) return false;
        }
        return true;
      })
      .sort((a, b) => {
        let valA: number = 0;
        let valB: number = 0;

        if (sortField === "forecast_24h") {
          valA = a.forecast_probabilities?.["24h"] ?? -1;
          valB = b.forecast_probabilities?.["24h"] ?? -1;
        } else if (sortField === "risk_score") {
          valA = a.risk_score ?? 0;
          valB = b.risk_score ?? 0;
        } else if (sortField === "anomaly") {
          valA = a.anomaly_score ?? 0;
          valB = b.anomaly_score ?? 0;
        } else if (sortField === "rainfall") {
          valA = a.rainfall_24h ?? 0;
          valB = b.rainfall_24h ?? 0;
        } else if (sortField === "name") {
          const cmp = a.name.localeCompare(b.name);
          return sortOrder === "asc" ? cmp : -cmp;
        } else if (sortField === "trend") {
          const weights: Record<string, number> = { INCREASING: 3, VOLATILE: 2, STABLE: 1, DECREASING: 0 };
          const trendA = (a.trajectory || a.trend_direction || "STABLE").toUpperCase();
          const trendB = (b.trajectory || b.trend_direction || "STABLE").toUpperCase();
          valA = weights[trendA] ?? 1;
          valB = weights[trendB] ?? 1;
        }

        if (valA < valB) return sortOrder === "asc" ? -1 : 1;
        if (valA > valB) return sortOrder === "asc" ? 1 : -1;
        return 0;
      });
  }, [locations, filterLevel, filterTrend, sortField, sortOrder, searchQuery]);

  const getTrendIcon = (trajectory?: string, trendDir?: string) => {
    const t = (trajectory || trendDir || "STABLE").toUpperCase();
    if (t === "INCREASING" || t === "ESCALATING") {
      return <TrendingUp className="w-3.5 h-3.5 text-red-400" />;
    }
    if (t === "DECREASING" || t === "REDUCING") {
      return <TrendingDown className="w-3.5 h-3.5 text-emerald-400" />;
    }
    return <Minus className="w-3.5 h-3.5 text-zinc-500" />;
  };

  return (
    <div className="bg-black border border-zinc-800 rounded-lg shadow-xl overflow-hidden font-sans">
      {/* Header */}
      <div className="p-3 bg-zinc-950 border-b border-zinc-850 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2.5">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-black text-white tracking-wide uppercase font-mono">
              NER Landslide Early Warning Priority
            </h2>
            <p className="text-[11px] text-zinc-400 font-mono">
              Ranked by 24h ML prediction probability and deterministic physical thresholds
            </p>
          </div>
        </div>

        {/* Filter & Search Toolbar */}
        <div className="flex items-center gap-2 flex-wrap">
          <input
            type="text"
            placeholder="Search station..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-zinc-900 border border-zinc-750 text-zinc-200 text-xs px-2.5 py-1 rounded focus:outline-none focus:border-zinc-500 font-mono w-32 sm:w-40"
          />

          <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-750 px-2 py-1 rounded text-xs font-mono">
            <span className="text-zinc-400 text-[10px]">Tier:</span>
            <select
              value={filterLevel}
              onChange={(e) => setFilterLevel(e.target.value)}
              className="bg-transparent text-white font-bold focus:outline-none cursor-pointer text-xs"
            >
              <option value="ALL" className="bg-zinc-950">ALL</option>
              <option value="CRITICAL" className="bg-zinc-950 text-red-400">CRITICAL</option>
              <option value="HIGH" className="bg-zinc-950 text-orange-400">HIGH</option>
              <option value="MODERATE" className="bg-zinc-950 text-amber-400">MODERATE</option>
              <option value="LOW" className="bg-zinc-950 text-emerald-400">LOW</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono divide-y divide-zinc-850">
          <thead className="bg-zinc-900/90 text-zinc-400 text-[10px] uppercase tracking-wider font-bold">
            <tr>
              <th className="px-3 py-2.5">#</th>
              <th className="px-3 py-2.5 cursor-pointer hover:text-white" onClick={() => handleSort("name")}>
                Station / Sector {sortField === "name" && (sortOrder === "asc" ? "▲" : "▼")}
              </th>
              <th className="px-3 py-2.5 cursor-pointer text-emerald-400 hover:text-white" onClick={() => handleSort("forecast_24h")}>
                24H ML Forecast {sortField === "forecast_24h" && (sortOrder === "asc" ? "▲" : "▼")}
              </th>
              <th className="px-3 py-2.5 cursor-pointer hover:text-white" onClick={() => handleSort("risk_score")}>
                Current Risk {sortField === "risk_score" && (sortOrder === "asc" ? "▲" : "▼")}
              </th>
              <th className="px-3 py-2.5 cursor-pointer hover:text-white" onClick={() => handleSort("anomaly")}>
                Anomaly {sortField === "anomaly" && (sortOrder === "asc" ? "▲" : "▼")}
              </th>
              <th className="px-3 py-2.5 cursor-pointer hover:text-white" onClick={() => handleSort("trend")}>
                Trend {sortField === "trend" && (sortOrder === "asc" ? "▲" : "▼")}
              </th>
              <th className="px-3 py-2.5">Freshness</th>
              <th className="px-3 py-2.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-850 bg-black">
            {filteredAndSortedLocations.map((loc, idx) => {
              const isSelected = loc.id === selectedLocationId;
              const p24 = loc.forecast_probabilities?.["24h"];
              const p24Pct = p24 !== undefined && p24 !== null ? Math.round(p24 * 100) : null;

              return (
                <tr
                  key={loc.id}
                  onClick={() => onSelectLocation(loc.id)}
                  className={`cursor-pointer transition ${
                    isSelected
                      ? "bg-zinc-800/80 text-white"
                      : "hover:bg-zinc-900/70 text-zinc-300"
                  }`}
                >
                  <td className="px-3 py-2.5 font-bold text-zinc-400">
                    <span className={`inline-flex items-center justify-center w-5 h-5 rounded text-[10px] ${
                      idx === 0 ? "bg-red-950 text-red-300 border border-red-700 font-black" : "bg-zinc-900 text-zinc-300 border border-zinc-800"
                    }`}>
                      {idx + 1}
                    </span>
                  </td>

                  <td className="px-3 py-2.5">
                    <div className="font-bold text-white flex items-center gap-1.5">
                      {loc.name}
                      {loc.active_event && (
                        <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />
                      )}
                    </div>
                    <div className="text-[10px] text-zinc-500">
                      {loc.district}, {loc.state}
                    </div>
                  </td>

                  {/* 24H ML Forecast Probability */}
                  <td className="px-3 py-2.5">
                    {p24Pct !== null ? (
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded font-black text-xs ${
                          p24Pct >= 70 ? "bg-red-950 text-red-300 border border-red-800" :
                          p24Pct >= 50 ? "bg-orange-950 text-orange-300 border border-orange-800" :
                          p24Pct >= 30 ? "bg-amber-950 text-amber-300 border border-amber-800" :
                          "bg-emerald-950 text-emerald-300 border border-emerald-800"
                        }`}>
                          {p24Pct}%
                        </span>
                        <div className="w-12 bg-zinc-900 h-1.5 rounded-full overflow-hidden hidden sm:block">
                          <div
                            className={`h-full ${
                              p24Pct >= 70 ? "bg-red-500" :
                              p24Pct >= 50 ? "bg-orange-500" :
                              p24Pct >= 30 ? "bg-yellow-400" : "bg-emerald-500"
                            }`}
                            style={{ width: `${Math.min(100, p24Pct)}%` }}
                          />
                        </div>
                      </div>
                    ) : (
                      <span className="text-zinc-600 text-[10px]">UNAVAILABLE</span>
                    )}
                  </td>

                  {/* Deterministic Risk Condition */}
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-1.5">
                      <span className="font-black text-white">{loc.risk_score.toFixed(0)}</span>
                      <span className="text-[10px] text-zinc-500">/100</span>
                      <span className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${
                        loc.risk_level === "CRITICAL" ? "text-red-400" :
                        loc.risk_level === "HIGH" ? "text-orange-400" :
                        loc.risk_level === "MODERATE" ? "text-amber-400" :
                        "text-emerald-400"
                      }`}>
                        ({loc.risk_level})
                      </span>
                    </div>
                  </td>

                  {/* Anomaly Status */}
                  <td className="px-3 py-2.5">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                      loc.anomaly_level === "SEVERE" ? "bg-red-950 text-red-300 border border-red-800" :
                      loc.anomaly_level === "ELEVATED" ? "bg-amber-950 text-amber-300 border border-amber-800" :
                      "bg-zinc-900 text-zinc-400 border border-zinc-800"
                    }`}>
                      {loc.anomaly_level || "NORMAL"}
                    </span>
                  </td>

                  {/* Trend */}
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-1">
                      {getTrendIcon(loc.trajectory, loc.trend_direction)}
                      <span className="text-[10px] text-zinc-400">
                        {loc.trajectory || loc.trend_direction || "STABLE"}
                      </span>
                    </div>
                  </td>

                  {/* Data Freshness */}
                  <td className="px-3 py-2.5">
                    <span className={`text-[10px] font-bold ${
                      loc.data_freshness === "FRESH" ? "text-emerald-400" :
                      loc.data_freshness === "AGING" ? "text-amber-400" : "text-red-400"
                    }`}>
                      {loc.data_freshness || "FRESH"}
                    </span>
                  </td>

                  {/* Actions */}
                  <td className="px-3 py-2.5 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenInvestigate(loc.id);
                      }}
                      className="px-2 py-1 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white rounded border border-zinc-700 text-[10px] font-bold inline-flex items-center gap-1 transition"
                      title="Investigate Station 360"
                    >
                      <Eye className="w-3 h-3" />
                      <span>Investigate</span>
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
