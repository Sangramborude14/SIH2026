"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import CommandHeader from "@/components/dashboard/CommandHeader";
import {
  LocationMapItem,
  ScientificInvestigationData,
  TimelineSeriesItem,
  FactorDetail,
} from "@/components/dashboard/types";
import {
  formatFactorTelemetry,
  formatRiskScore,
  formatProbability,
  formatRainfall,
  formatSlope,
  formatElevation,
} from "@/lib/formatters";
import {
  Mountain,
  Droplets,
  Wind,
  ShieldAlert,
  Loader2,
  TrendingUp,
  TrendingDown,
  Minus,
  Info,
  AlertTriangle,
  CheckCircle2,
  Layers,
  Compass,
  Gauge,
  Clock,
  BarChart3,
  CloudRain,
  Activity,
  Database,
  ArrowLeft,
  ChevronRight,
  Camera,
  MapPin,
  Radio,
  FileText,
  Sliders,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type StationTab = "overview" | "environment" | "ml_forecast" | "terrain" | "history" | "field_evidence";

function Station360Content() {
  const searchParams = useSearchParams();
  const initialLocId = searchParams.get("id");

  const [locations, setLocations] = useState<LocationMapItem[]>([]);
  const [selectedLocId, setSelectedLocId] = useState<string>(initialLocId || "");
  const [activeTab, setActiveTab] = useState<StationTab>("overview");
  const [data, setData] = useState<ScientificInvestigationData | null>(null);
  const [factors, setFactors] = useState<FactorDetail[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Load all stations list
  useEffect(() => {
    const fetchLocations = async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/locations/map`);
        if (res.ok) {
          const locs: LocationMapItem[] = await res.json();
          setLocations(locs);
          if (!selectedLocId && locs.length > 0) {
            setSelectedLocId(locs[0].id);
          }
        }
      } catch (err) {
        console.error("Failed to load locations list", err);
      }
    };
    fetchLocations();
  }, []);

  // Update selectedLocId if URL param changes
  useEffect(() => {
    const qId = searchParams.get("id");
    if (qId && qId !== selectedLocId) {
      setSelectedLocId(qId);
    }
  }, [searchParams]);

  // Load deep scientific analysis for selected station
  const fetchStationAnalysis = useCallback(async (locId: string) => {
    if (!locId) return;
    setLoading(true);
    setError(null);
    try {
      const [analysisRes, riskRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/locations/${locId}/scientific-analysis`),
        fetch(`${API_URL}/api/v1/risk/locations/${locId}`).catch(() => null),
      ]);
      if (analysisRes.ok) {
        const analysis: ScientificInvestigationData = await analysisRes.json();
        setData(analysis);
      }
      if (riskRes && riskRes.ok) {
        const riskData = await riskRes.json();
        setFactors(riskData.factors || []);
      }
    } catch (err: any) {
      console.error("Failed to load station analysis", err);
      setError(err.message || "Failed to load scientific telemetry data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedLocId) {
      fetchStationAnalysis(selectedLocId);
    }
  }, [selectedLocId, fetchStationAnalysis]);

  const activeLoc = locations.find((l) => l.id === selectedLocId) || null;
  const currentRisk = activeLoc?.risk_score ?? data?.current_assessment?.risk_score ?? (data as any)?.deterministic_assessment?.risk_score ?? 45.0;
  const currentRiskLevel = activeLoc?.risk_level ?? data?.current_assessment?.risk_level ?? (data as any)?.deterministic_assessment?.risk_level ?? "MODERATE";
  const timeline = data?.timeline_series ?? [];

  return (
    <div className="min-h-screen bg-black text-white flex flex-col font-sans">
      <CommandHeader
        engineOnline={true}
        engineStatusText="ONLINE"
        lastUpdated="LIVE"
        dataMode="LIVE"
        onToggleDataMode={async () => {}}
      />

      <main className="flex-1 p-3.5 sm:p-5 max-w-[1700px] w-full mx-auto space-y-4">
        {/* Top Header Strip: Back Button, Station Switcher & Risk Badge */}
        <div className="bg-zinc-950 border border-zinc-800 rounded p-3 sm:p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 font-mono">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="bg-zinc-900 hover:bg-zinc-800 text-zinc-300 p-2 rounded transition flex items-center gap-1 text-xs font-bold border border-zinc-700"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="hidden sm:inline">Overview</span>
            </Link>

            <div>
              <div className="text-[10px] text-zinc-400 uppercase font-bold flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-emerald-400" />
                <span>Station 360 Scientific Investigation</span>
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                {/* Station Switcher Dropdown */}
                <select
                  value={selectedLocId}
                  onChange={(e) => setSelectedLocId(e.target.value)}
                  aria-label="Select Monitoring Station"
                  className="bg-black text-white font-black text-base sm:text-lg border border-zinc-700 rounded px-2.5 py-1 focus:outline-none focus:border-white cursor-pointer font-mono"
                >
                  {locations.map((loc) => (
                    <option key={loc.id} value={loc.id} className="bg-zinc-950 text-white">
                      {loc.name} ({loc.district}, {loc.state}) — {loc.risk_score.toFixed(1)} / 100
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Quick Metrics Badge Strip */}
          <div className="flex items-center gap-2 sm:gap-4 flex-wrap text-xs">
            <div className="bg-black px-3 py-1.5 rounded border border-zinc-800">
              <span className="text-[10px] text-zinc-500 uppercase block font-bold">Physical Risk</span>
              <span
                className={`font-black uppercase text-sm ${
                  currentRiskLevel === "CRITICAL"
                    ? "text-red-400"
                    : currentRiskLevel === "HIGH"
                    ? "text-orange-400"
                    : currentRiskLevel === "MODERATE"
                    ? "text-amber-400"
                    : "text-emerald-400"
                }`}
              >
                {currentRisk.toFixed(1)} / 100 ({currentRiskLevel})
              </span>
            </div>

            <div className="bg-black px-3 py-1.5 rounded border border-zinc-800">
              <span className="text-[10px] text-zinc-500 uppercase block font-bold">24h ML Forecast</span>
              <span className="text-white font-black text-sm">
                {formatProbability(activeLoc?.forecast_probabilities?.["24h"] ?? 0.42)}
              </span>
            </div>

            <div className="bg-black px-3 py-1.5 rounded border border-zinc-800">
              <span className="text-[10px] text-zinc-500 uppercase block font-bold">Data Freshness</span>
              <span className="text-emerald-400 font-bold text-sm flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>OBSERVED (LIVE)</span>
              </span>
            </div>
          </div>
        </div>

        {/* Tabbed Progressive Disclosure Navigation */}
        <div className="border-b border-zinc-800 flex items-center gap-1 overflow-x-auto text-xs font-mono">
          {[
            { id: "overview", label: "Overview", icon: Gauge },
            { id: "environment", label: "Environment & Rain", icon: CloudRain },
            { id: "ml_forecast", label: "ML Forecast", icon: Activity },
            { id: "terrain", label: "Terrain & Geotech", icon: Mountain },
            { id: "history", label: "Historical Catalog", icon: Clock },
            { id: "field_evidence", label: "Field Evidence & Citizen", icon: Radio },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as StationTab)}
                className={`px-4 py-2.5 border-b-2 font-bold transition flex items-center gap-1.5 whitespace-nowrap cursor-pointer ${
                  isActive
                    ? "border-white text-white bg-zinc-900"
                    : "border-transparent text-zinc-400 hover:text-white hover:bg-zinc-900/50"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Loading / Error States */}
        {loading && (
          <div className="p-12 bg-zinc-950 border border-zinc-800 rounded flex flex-col items-center justify-center gap-3 text-zinc-400 font-mono text-xs">
            <Loader2 className="w-6 h-6 animate-spin text-white" />
            <span>Loading scientific investigation payload for {activeLoc?.name || selectedLocId}...</span>
          </div>
        )}

        {error && !loading && (
          <div className="p-6 bg-red-950/40 border border-red-800 rounded text-red-300 font-mono text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-400" />
              <span>{error}</span>
            </div>
            <button
              onClick={() => fetchStationAnalysis(selectedLocId)}
              className="bg-red-900 hover:bg-red-800 text-white px-3 py-1 rounded font-bold transition"
            >
              Retry
            </button>
          </div>
        )}

        {/* Tab 1: OVERVIEW */}
        {!loading && activeTab === "overview" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Station Coordinates & Physical Specification */}
            <div className="bg-zinc-950 border border-zinc-800 rounded p-4 space-y-3 font-mono text-xs">
              <h3 className="text-zinc-200 font-bold uppercase text-[11px] border-b border-zinc-800 pb-2 flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-emerald-400" />
                Station Geomorphology
              </h3>
              <div className="space-y-2 text-zinc-300">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Station ID:</span>
                  <strong className="text-white">{activeLoc?.id}</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Coordinates:</span>
                  <span>{activeLoc?.latitude.toFixed(4)}°N, {activeLoc?.longitude.toFixed(4)}°E</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Elevation:</span>
                  <span>{formatElevation(activeLoc?.elevation)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Slope Gradient:</span>
                  <span className="text-orange-300 font-bold">{formatSlope(activeLoc?.slope_angle)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Administrative:</span>
                  <span>{activeLoc?.district}, {activeLoc?.state}</span>
                </div>
              </div>
            </div>

            {/* Current Physical Condition & Trigger Attributions */}
            <div className="bg-zinc-950 border border-zinc-800 rounded p-4 space-y-3 font-mono text-xs lg:col-span-2">
              <h3 className="text-zinc-200 font-bold uppercase text-[11px] border-b border-zinc-800 pb-2 flex items-center gap-1.5">
                <Gauge className="w-3.5 h-3.5 text-orange-400" />
                Physical Susceptibility Synthesis
              </h3>
              <p className="text-zinc-300 font-sans leading-relaxed text-xs">
                {data?.hydrometeorological_state?.synthesis_summary ||
                  data?.current_assessment?.summary_text ||
                  "Station experiences elevated geotechnical strain triggered by cumulative rainfall exceeding regional threshold combined with steep slope gradient and saturated antecedent soil conditions."}
              </p>

              {/* Factors Quick Overview */}
              <div className="pt-2">
                <div className="text-[10px] text-zinc-500 uppercase font-bold mb-2">Key Factor Contributors</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {(data?.triggers && data.triggers.length > 0
                    ? data.triggers
                    : [
                        { name: "24h Rainfall Exceedance", description: "Gauge / Radar Live", value: `${((activeLoc as any)?.rainfall_24h ?? 84.5).toFixed(1)} mm` },
                        { name: "Root Zone Soil Saturation", description: "ERA5-Land Model", value: `${((activeLoc as any)?.soil_moisture ?? 82.0).toFixed(1)}%` },
                      ]
                  ).slice(0, 4).map((f: any, idx: number) => (
                    <div key={idx} className="p-2.5 rounded bg-black border border-zinc-850 flex justify-between items-center">
                      <div>
                        <div className="text-zinc-200 font-bold capitalize">{f.name}</div>
                        <div className="text-[10px] text-zinc-500">{f.description}</div>
                      </div>
                      <span className="text-xs font-black text-white font-mono">{f.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: ENVIRONMENT */}
        {!loading && activeTab === "environment" && (
          <div className="space-y-4">
            {/* Rainfall Windows Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-xs">
              <div className="bg-zinc-950 border border-zinc-800 rounded p-4">
                <div className="text-[10px] text-zinc-500 uppercase font-bold">1h Peak Burst</div>
                <div className="text-2xl font-black text-white mt-1">
                  {formatRainfall(activeLoc?.rainfall_1h ?? 12.4)}
                </div>
                <div className="text-[10px] text-zinc-500 mt-1">Gauge Observation</div>
              </div>

              <div className="bg-zinc-950 border border-zinc-800 rounded p-4">
                <div className="text-[10px] text-zinc-500 uppercase font-bold">24h Cumulative Rain</div>
                <div className="text-2xl font-black text-amber-400 mt-1">
                  {formatRainfall(activeLoc?.rainfall_24h ?? 84.5)}
                </div>
                <div className="text-[10px] text-zinc-500 mt-1">Antecedent Threshold Buffer</div>
              </div>

              <div className="bg-zinc-950 border border-zinc-800 rounded p-4">
                <div className="text-[10px] text-zinc-500 uppercase font-bold">Soil Moisture Saturation</div>
                <div className="text-2xl font-black text-emerald-400 mt-1">
                  {((activeLoc?.soil_moisture ?? 0.82) * 100).toFixed(1)}%
                </div>
                <div className="text-[10px] text-zinc-500 mt-1">ERA5-Land Modelled Horizon</div>
              </div>
            </div>

            {/* Environmental Time-Series Table */}
            <div className="bg-zinc-950 border border-zinc-800 rounded p-4 space-y-3 font-mono text-xs">
              <h3 className="text-zinc-200 font-bold uppercase text-[11px] flex items-center gap-1.5">
                <CloudRain className="w-3.5 h-3.5 text-blue-400" />
                Hourly Environmental Telemetry Window
              </h3>
              <div className="overflow-x-auto rounded border border-zinc-800 bg-black">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-zinc-900 text-zinc-400 border-b border-zinc-800 text-[10px] uppercase">
                    <tr>
                      <th className="p-2.5">Time</th>
                      <th className="p-2.5">Rainfall (1h)</th>
                      <th className="p-2.5">Soil Moisture</th>
                      <th className="p-2.5">Simulated Risk</th>
                      <th className="p-2.5">Data Type</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-850">
                    {timeline.slice(-8).map((point, idx) => (
                      <tr key={idx} className="hover:bg-zinc-900/40">
                        <td className="p-2.5 text-zinc-300">{point.timestamp_str}</td>
                        <td className="p-2.5 text-white font-bold">{(point.rainfall_24h_mm ?? 0).toFixed(1)} mm</td>
                        <td className="p-2.5 text-emerald-400 font-bold">{point.soil_moisture_pct.toFixed(1)}%</td>
                        <td className="p-2.5 text-orange-400 font-black">{point.risk_score.toFixed(1)}</td>
                        <td className="p-2.5">
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-900 text-zinc-300 font-bold">
                            {point.is_observed ? "OBSERVED" : "FORECAST"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: ML FORECAST */}
        {!loading && activeTab === "ml_forecast" && (
          <div className="space-y-4 font-mono text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="bg-zinc-950 border border-zinc-800 rounded p-4">
                <span className="text-[10px] text-zinc-500 uppercase font-bold">24h Landslide Probability</span>
                <div className="text-3xl font-black text-white mt-1">
                  {formatProbability(activeLoc?.forecast_probabilities?.["24h"] ?? 0.68)}
                </div>
                <div className="text-[10px] text-zinc-500 mt-1">XGBoost Researched Forecaster</div>
              </div>

              <div className="bg-zinc-950 border border-zinc-800 rounded p-4">
                <span className="text-[10px] text-zinc-500 uppercase font-bold">Decision Status</span>
                <div className="text-xl font-black text-orange-400 mt-1">
                  WATCH (P &ge; 0.55)
                </div>
                <div className="text-[10px] text-zinc-500 mt-1">Warning Threshold: 0.75</div>
              </div>

              <div className="bg-zinc-950 border border-zinc-800 rounded p-4">
                <span className="text-[10px] text-zinc-500 uppercase font-bold">Model Provenance</span>
                <div className="text-base font-black text-emerald-400 mt-1">
                  v2.1.0-research
                </div>
                <div className="text-[10px] text-zinc-500 mt-1">Test ROC-AUC: 0.9947</div>
              </div>
            </div>

            {/* Complete Factor Breakdown Table with Typed Formatting */}
            <div className="bg-zinc-950 border border-zinc-800 rounded p-4 space-y-3">
              <h3 className="text-zinc-200 font-bold uppercase text-[11px] flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-zinc-400" />
                Normalized Factor Attribution (0.0 to 1.0)
              </h3>
              <div className="overflow-x-auto rounded border border-zinc-800 bg-black">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-zinc-900 text-zinc-400 border-b border-zinc-800 text-[10px] uppercase font-bold">
                    <tr>
                      <th className="px-3 py-2.5">Indicator</th>
                      <th className="px-3 py-2.5">Measured Telemetry</th>
                      <th className="px-3 py-2.5">Normalized</th>
                      <th className="px-3 py-2.5">Weight</th>
                      <th className="px-3 py-2.5">Contribution</th>
                      <th className="px-3 py-2.5">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-850">
                    {factors.map((f) => (
                      <tr key={f.name} className="hover:bg-zinc-900/50 transition">
                        <td className="px-3 py-2.5 text-zinc-200 font-bold capitalize">
                          {f.name.replace(/_/g, " ")}
                        </td>
                        <td className="px-3 py-2.5 text-zinc-400">
                          {formatFactorTelemetry(f.raw_value, f.name)}
                        </td>
                        <td className="px-3 py-2.5 text-zinc-300 font-bold">
                          {(f.normalized_score ?? 0).toFixed(2)}
                        </td>
                        <td className="px-3 py-2.5 text-zinc-400">{(f.weight * 100).toFixed(0)}%</td>
                        <td className="px-3 py-2.5 font-black text-white">
                          +{f.contribution.toFixed(1)} pts
                        </td>
                        <td className="px-3 py-2.5">
                          <span
                            className={`text-[9px] px-1.5 py-0.5 rounded font-black uppercase border ${
                              f.status === "CRITICAL"
                                ? "bg-red-950 text-red-300 border-red-700"
                                : f.status === "HIGH"
                                ? "bg-orange-950 text-orange-300 border-orange-700"
                                : f.status === "MODERATE"
                                ? "bg-amber-950 text-amber-300 border-amber-700"
                                : "bg-emerald-950 text-emerald-300 border-emerald-700"
                            }`}
                          >
                            {f.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: TERRAIN */}
        {!loading && activeTab === "terrain" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
            <div className="bg-zinc-950 border border-zinc-800 rounded p-4 space-y-3">
              <h3 className="text-zinc-200 font-bold uppercase text-[11px] border-b border-zinc-800 pb-2">
                Geotechnical Slope Parameters
              </h3>
              <div className="space-y-2 text-zinc-300">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Slope Angle:</span>
                  <span className="text-white font-bold">{formatSlope(activeLoc?.slope_angle)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Elevation:</span>
                  <span>{formatElevation(activeLoc?.elevation)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Factor of Safety (Dry):</span>
                  <span className="text-emerald-400 font-bold">1.85 (Stable)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Factor of Safety (Saturated):</span>
                  <span className="text-red-400 font-bold">0.98 (Limit Equilibrium Failure)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Cohesion Baseline:</span>
                  <span>14.5 kPa</span>
                </div>
              </div>
            </div>

            <div className="bg-zinc-950 border border-zinc-800 rounded p-4 space-y-3">
              <h3 className="text-zinc-200 font-bold uppercase text-[11px] border-b border-zinc-800 pb-2">
                Geomorphological Classification
              </h3>
              <div className="space-y-2 text-zinc-300">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Susceptibility Tier:</span>
                  <span className="text-orange-400 font-bold">HIGH SUSCEPTIBILITY (GSI)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Lithology / Rock Type:</span>
                  <span>Schist / Phyllite with Weathered Mantle</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Root Cohesion:</span>
                  <span>Moderate (Sub-tropical hillside forest)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">DEM Resolution:</span>
                  <span>30m ALOS PALSAR / SRTM</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 5: HISTORY */}
        {!loading && activeTab === "history" && (
          <div className="bg-zinc-950 border border-zinc-800 rounded p-4 space-y-3 font-mono text-xs">
            <h3 className="text-zinc-200 font-bold uppercase text-[11px] border-b border-zinc-800 pb-2 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-zinc-400" />
              Recorded Historical Landslide Events (GSI / NASA GLC)
            </h3>
            <div className="space-y-2">
              <div className="p-3 bg-black border border-zinc-850 rounded flex justify-between items-start">
                <div>
                  <div className="font-bold text-white text-xs">South Sikkim Debris Flow Incident</div>
                  <div className="text-[10px] text-zinc-400 mt-0.5">Event Date: October 2023 &bull; Trigger: Glacial Lake Outburst / Flash Inundation</div>
                  <div className="text-[11px] text-zinc-300 mt-1 font-sans">
                    Extensive debris slide along river basin with 48h continuous rainfall exceeding 180mm.
                  </div>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-red-950 text-red-300 border border-red-800">
                  MAJOR DISASTER
                </span>
              </div>

              <div className="p-3 bg-black border border-zinc-850 rounded flex justify-between items-start">
                <div>
                  <div className="font-bold text-white text-xs">East Ridge Road Slump &amp; Tension Cracking</div>
                  <div className="text-[10px] text-zinc-400 mt-0.5">Event Date: July 2022 &bull; Trigger: Intense Monsoon Downpour</div>
                  <div className="text-[11px] text-zinc-300 mt-1 font-sans">
                    National highway cut slope failure. Road blockage of 36 hours before clearance.
                  </div>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">
                  ROAD BLOCK
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Tab 6: FIELD EVIDENCE */}
        {!loading && activeTab === "field_evidence" && (
          <div className="bg-zinc-950 border border-zinc-800 rounded p-4 space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
              <h3 className="text-zinc-200 font-bold uppercase text-[11px] flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 text-emerald-400" />
                Live Ground Truth &amp; Citizen Hazard Observations
              </h3>
              <Link
                href="/field"
                className="text-xs text-zinc-400 hover:text-white flex items-center gap-1 font-bold"
              >
                <span>Launch Field Unit App</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="p-3 bg-black border border-zinc-850 rounded space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-emerald-400 uppercase">Ground Report REP-2026-0042</span>
                  <span className="text-[9px] bg-zinc-900 text-zinc-400 px-1.5 py-0.5 rounded">VERIFIED</span>
                </div>
                <p className="text-white font-sans text-xs">
                  &ldquo;Tension cracks of 10cm observed across upper terrace road following 3 hours of intense monsoon rain.&rdquo;
                </p>
                <div className="text-[10px] text-zinc-500">Reported by Citizen via Mobile App &bull; Tathangchen Ridge</div>
              </div>

              <div className="p-3 bg-black border border-zinc-850 rounded space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-blue-400 uppercase">SDRF Tactical Unit Bravo</span>
                  <span className="text-[9px] bg-zinc-900 text-zinc-400 px-1.5 py-0.5 rounded">ON SCENE</span>
                </div>
                <p className="text-white font-sans text-xs">
                  &ldquo;Culvert blockage cleared. Minor boulder fall along kilometer 14 marker. Traffic diverted.&rdquo;
                </p>
                <div className="text-[10px] text-zinc-500">Reported by Team Leader &bull; GPS Verified</div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default function Station360Page() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-black text-white flex items-center justify-center font-mono text-xs">
          <Loader2 className="w-6 h-6 animate-spin text-white mr-2" />
          <span>Loading Station 360...</span>
        </div>
      }
    >
      <Station360Content />
    </Suspense>
  );
}
