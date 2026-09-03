"use client";

import React from "react";
import { LocationMapItem } from "./types";
import {
  Clock,
  ArrowRight,
  TrendingUp,
  Droplets,
  Mountain,
  ShieldCheck,
  AlertTriangle,
  Cpu,
  Sparkles,
  Info,
} from "lucide-react";

interface ForecastProgressionTimelineProps {
  location: LocationMapItem | null;
  onOpenInvestigate?: (locationId: string) => void;
}

export default function ForecastProgressionTimeline({
  location,
  onOpenInvestigate,
}: ForecastProgressionTimelineProps) {
  if (!location) {
    return (
      <div className="bg-black border border-zinc-800 rounded-lg p-4 font-mono text-zinc-500 text-xs flex items-center justify-center gap-2">
        <Info className="w-4 h-4" />
        Select a monitoring station to inspect chronological forecast progression.
      </div>
    );
  }

  const p24 = location.forecast_probabilities?.["24h"];
  const p24Pct = p24 !== undefined && p24 !== null ? Math.round(p24 * 100) : null;
  const detScore = Math.round(location.risk_score ?? 10);

  return (
    <div className="bg-black border border-zinc-800 rounded-lg p-4 font-sans shadow-xl space-y-3.5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-zinc-800 pb-2.5">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded bg-zinc-900 border border-zinc-750 text-white">
            <Clock className="w-4 h-4 text-emerald-400" />
          </div>
          <div>
            <div className="text-xs font-black uppercase tracking-wider text-white font-mono flex items-center gap-1.5">
              Landslide Hazard Progression: Past &rarr; Now &rarr; Future
            </div>
            <div className="text-[11px] text-zinc-400 font-mono">
              Station: <strong className="text-white">{location.name}</strong> ({location.district}, {location.state})
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 font-mono text-[10px]">
          <span className="text-zinc-500">Data Freshness:</span>
          <span className={`px-2 py-0.5 rounded font-bold ${
            location.data_freshness === "FRESH" ? "bg-emerald-950 text-emerald-300 border border-emerald-800" :
            location.data_freshness === "AGING" ? "bg-amber-950 text-amber-300 border border-amber-800" :
            "bg-red-950 text-red-300 border border-red-800"
          }`}>
            {location.data_freshness || "FRESH"}
          </span>
        </div>
      </div>

      {/* Progression Cards Grid (3 Columns) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* Step 1: PAST (Observed Hydrological Telemetry) */}
        <div className="bg-zinc-950 border border-zinc-850 rounded-lg p-3 space-y-2 font-mono">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase text-zinc-400">1. Past Observations</span>
            <span className="text-[10px] text-zinc-500">In-situ Sensors</span>
          </div>
          <div className="space-y-1.5 text-xs">
            <div className="flex items-center justify-between bg-black p-1.5 rounded border border-zinc-850">
              <span className="text-zinc-400 flex items-center gap-1">
                <Droplets className="w-3.5 h-3.5 text-blue-400" /> 24h Rainfall:
              </span>
              <span className="font-bold text-white">{location.rainfall_24h ?? 0} mm</span>
            </div>
            <div className="flex items-center justify-between bg-black p-1.5 rounded border border-zinc-850">
              <span className="text-zinc-400 flex items-center gap-1">
                <Mountain className="w-3.5 h-3.5 text-amber-400" /> Soil Saturation:
              </span>
              <span className="font-bold text-white">{location.soil_moisture ?? "--"}%</span>
            </div>
            <div className="flex items-center justify-between bg-black p-1.5 rounded border border-zinc-850">
              <span className="text-zinc-400">Slope Gradient:</span>
              <span className="font-bold text-white">{location.slope_angle ?? 30}°</span>
            </div>
          </div>
        </div>

        {/* Step 2: NOW (Current Deterministic Landslide Condition) */}
        <div className="bg-zinc-950 border border-zinc-850 rounded-lg p-3 space-y-2 font-mono relative">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase text-zinc-400">2. Current Condition (NOW)</span>
            <span className="text-[10px] text-zinc-500">Physics Baseline</span>
          </div>
          <div className="p-2.5 rounded bg-black border border-zinc-850 text-center space-y-1">
            <div className="text-[10px] text-zinc-400 uppercase font-bold">Deterministic Risk Score</div>
            <div className="text-2xl font-black text-white">
              {detScore}
              <span className="text-xs text-zinc-500 font-normal"> / 100</span>
            </div>
            <span className={`inline-block px-2 py-0.5 rounded text-xs font-black ${
              location.risk_level === "CRITICAL" ? "bg-red-950 text-red-300 border border-red-800" :
              location.risk_level === "HIGH" ? "bg-orange-950 text-orange-300 border border-orange-800" :
              location.risk_level === "MODERATE" ? "bg-amber-950 text-amber-300 border border-amber-800" :
              "bg-emerald-950 text-emerald-300 border border-emerald-800"
            }`}>
              {location.risk_level} SEVERITY
            </span>
          </div>
        </div>

        {/* Step 3: FUTURE (Calibrated ML Forecast Probability) */}
        <div className="bg-zinc-950 border border-emerald-950/60 rounded-lg p-3 space-y-2 font-mono">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase text-emerald-400 flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-emerald-400" /> 3. ML Forecast (24H FUTURE)
            </span>
            <span className="text-[10px] text-zinc-500">{location.model_version || "v2.0.0"}</span>
          </div>
          <div className="p-2.5 rounded bg-black border border-zinc-850 text-center space-y-1">
            <div className="text-[10px] text-zinc-400 uppercase font-bold">Landslide Occurrence Probability</div>
            {p24Pct !== null ? (
              <>
                <div className="text-2xl font-black text-white">
                  {p24Pct}%
                </div>
                <div className="w-full bg-zinc-900 h-1.5 rounded-full overflow-hidden my-1">
                  <div
                    className={`h-full ${
                      p24Pct >= 70 ? "bg-red-500" :
                      p24Pct >= 50 ? "bg-orange-500" :
                      p24Pct >= 30 ? "bg-yellow-400" : "bg-emerald-500"
                    }`}
                    style={{ width: `${Math.min(100, p24Pct)}%` }}
                  />
                </div>
                <span className={`inline-block text-[10px] font-bold ${
                  p24Pct >= 50 ? "text-red-400" : "text-emerald-400"
                }`}>
                  {p24Pct >= 50 ? "Decision Threshold (50%) Exceeded" : "Below Decision Threshold"}
                </span>
              </>
            ) : (
              <div className="py-2 text-zinc-600 text-xs font-bold">
                ML FORECAST UNAVAILABLE
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Semantic Distinction Disclaimer */}
      <div className="bg-zinc-950/60 border border-zinc-850 rounded p-2 text-[10px] font-mono text-zinc-500 flex items-center justify-between">
        <span>
          <strong className="text-zinc-400">Scientific Distinction:</strong> Deterministic Risk (0-100) measures present physical susceptibility. ML Probability ($0-100\%$) forecasts upcoming failure occurrence over the 24-hour window.
        </span>
        {onOpenInvestigate && (
          <button
            onClick={() => onOpenInvestigate(location.id)}
            className="text-emerald-400 hover:text-emerald-300 font-bold underline whitespace-nowrap ml-2"
          >
            Station 360 &rarr;
          </button>
        )}
      </div>
    </div>
  );
}
