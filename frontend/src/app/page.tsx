"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  DashboardSummaryData,
  LocationMapItem,
  DisasterEventItem,
} from "@/components/dashboard/types";
import CommandHeader from "@/components/dashboard/CommandHeader";
import KPICards from "@/components/dashboard/KPICards";
import RiskMap from "@/components/dashboard/RiskMap";
import LocationPriorityTable from "@/components/dashboard/LocationPriorityTable";
import {
  AlertTriangle,
  AlertOctagon,
  ShieldAlert,
  ChevronRight,
  CheckCircle2,
  ExternalLink,
  MapPin,
  ArrowUpRight,
  Clock,
  Sparkles,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function CommandCenter() {
  const router = useRouter();

  // Operational state
  const [summary, setSummary] = useState<DashboardSummaryData | null>(null);
  const [locations, setLocations] = useState<LocationMapItem[]>([]);
  const [events, setEvents] = useState<DisasterEventItem[]>([]);
  const [dataMode, setDataMode] = useState<string>("LIVE");
  const [fieldSummary, setFieldSummary] = useState<any>(null);
  const [mlStatus, setMlStatus] = useState<{
    model_status: string;
    active_prediction_tier: string;
    active_model_version: string;
    is_trained: boolean;
  } | null>(null);

  // Selection state
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(null);
  const [engineOnline, setEngineOnline] = useState<boolean>(true);
  const [engineStatusText, setEngineStatusText] = useState<string>("ONLINE");
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isRunningEngine, setIsRunningEngine] = useState<boolean>(false);
  const [isIngesting, setIsIngesting] = useState<boolean>(false);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState<number>(30);
  const [acknowledgingId, setAcknowledgingId] = useState<string | null>(null);

  // Master refresh function
  const refreshDashboardData = useCallback(async () => {
    try {
      // 1. Fetch Summary & Engine Status in parallel
      const [sumRes, engRes, mapRes, evRes, mlRes, fieldRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/v1/dashboard/summary`),
        fetch(`${API_URL}/api/v1/engine/status`),
        fetch(`${API_URL}/api/v1/locations/map`),
        fetch(`${API_URL}/api/v1/events`),
        fetch(`${API_URL}/api/v1/ml/status`),
        fetch(`${API_URL}/api/v1/field/summary`),
      ]);

      if (engRes.status === "fulfilled" && engRes.value.ok) {
        const engData = await engRes.value.json();
        setEngineStatusText(engData.engine_status || "ONLINE");
        setEngineOnline(true);
      }

      if (sumRes.status === "fulfilled" && sumRes.value.ok) {
        const sumData: DashboardSummaryData = await sumRes.value.json();
        setSummary(sumData);
        setEngineOnline(true);
      } else if (engRes.status === "rejected" && sumRes.status === "rejected") {
        setEngineOnline(false);
        setEngineStatusText("OFFLINE");
      }

      // Map locations
      let mapData: LocationMapItem[] = [];
      if (mapRes.status === "fulfilled" && mapRes.value.ok) {
        mapData = await mapRes.value.json();
        setLocations(mapData);
      }

      // Active events
      if (evRes.status === "fulfilled" && evRes.value.ok) {
        const evData: DisasterEventItem[] = await evRes.value.json();
        setEvents(evData);
      }

      // Field summary
      if (fieldRes.status === "fulfilled" && fieldRes.value.ok) {
        const fData = await fieldRes.value.json();
        setFieldSummary(fData);
      }

      // ML status
      if (mlRes.status === "fulfilled" && mlRes.value.ok) {
        const mlData = await mlRes.value.json();
        setMlStatus({
          model_status: mlData.model_status || "NOT_TRAINED",
          active_prediction_tier: mlData.active_prediction_tier || "BASELINE_DETERMINISTIC",
          active_model_version: mlData.active_model_version || "2.1.0",
          is_trained: mlData.is_trained ?? true,
        });
      }

      // Sync fix timestamp
      const now = new Date();
      setLastUpdated(
        `${now.getUTCHours().toString().padStart(2, "0")}:${now.getUTCMinutes().toString().padStart(2, "0")}:${now
          .getUTCSeconds()
          .toString()
          .padStart(2, "0")} UTC`
      );

      // Auto-select highest risk location if none selected
      setSelectedLocationId((prev) => {
        if (prev && mapData.some((l) => l.id === prev)) return prev;
        if (mapData.length > 0) {
          const highest = [...mapData].sort((a, b) => b.risk_score - a.risk_score)[0];
          return highest.id;
        }
        return null;
      });
    } catch (err) {
      console.error("Dashboard refresh error:", err);
      setEngineOnline(false);
    }
  }, []);

  useEffect(() => {
    refreshDashboardData();
  }, [refreshDashboardData]);

  // Auto-refresh loop
  useEffect(() => {
    if (autoRefreshInterval <= 0) return;
    const interval = setInterval(refreshDashboardData, autoRefreshInterval * 1000);
    return () => clearInterval(interval);
  }, [autoRefreshInterval, refreshDashboardData]);

  // Toggle Live vs Simulation Mode
  const handleToggleDataMode = async (mode: string) => {
    try {
      const res = await fetch(`${API_URL}/api/v1/ingestion/mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      if (res.ok) {
        const data = await res.json();
        setDataMode(data.current_mode);
        await refreshDashboardData();
      }
    } catch (err) {
      console.error("Failed to toggle data mode:", err);
    }
  };

  // Trigger Ingest Batch
  const handleTriggerBatchIngest = async () => {
    setIsIngesting(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/ingestion/batch`, { method: "POST" });
      if (res.ok) await refreshDashboardData();
    } catch (err) {
      console.error("Batch ingestion error:", err);
    } finally {
      setIsIngesting(false);
    }
  };

  // Trigger Manual Engine Assessment
  const handleTriggerEngineRun = async () => {
    setIsRunningEngine(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/engine/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force_fresh_fetch: true }),
      });
      if (res.ok) await refreshDashboardData();
    } catch (err) {
      console.error("Engine run error:", err);
    } finally {
      setIsRunningEngine(false);
    }
  };

  // Acknowledge event
  const handleAcknowledgeEvent = async (eventId: string) => {
    setAcknowledgingId(eventId);
    try {
      const res = await fetch(`${API_URL}/api/v1/events/${eventId}/acknowledge`, { method: "POST" });
      if (res.ok) await refreshDashboardData();
    } catch (err) {
      console.error("Failed to acknowledge event:", err);
    } finally {
      setAcknowledgingId(null);
    }
  };

  // Navigate to Station 360
  const handleOpenStation360 = (locId: string) => {
    router.push(`/stations?id=${locId}`);
  };

  const activeAlerts = events.filter((e) => e.status !== "RESOLVED");
  const selectedLocation = locations.find((l) => l.id === selectedLocationId) || locations[0] || null;

  return (
    <div className="min-h-screen bg-black text-white flex flex-col font-sans">
      {/* 1. Standardized Command Header */}
      <CommandHeader
        engineOnline={engineOnline}
        engineStatusText={engineStatusText}
        lastUpdated={lastUpdated}
        dataSourcesStatus={summary?.data_sources_status || "OPEN-METEO LIVE / NER STATIONS"}
        dataMode={dataMode}
        onToggleDataMode={handleToggleDataMode}
        onTriggerEngineRun={handleTriggerEngineRun}
        onTriggerBatchIngest={handleTriggerBatchIngest}
        isRunningEngine={isRunningEngine}
        isIngesting={isIngesting}
        autoRefreshInterval={autoRefreshInterval}
        onToggleAutoRefresh={(sec) => setAutoRefreshInterval(sec)}
        fieldActiveCount={fieldSummary?.active_teams ?? 3}
        mlModelStatus={mlStatus?.model_status}
        mlModelVersion={mlStatus?.active_model_version}
        mlIsTrained={mlStatus?.is_trained ?? true}
      />

      {/* 2. Main Dashboard (Above-The-Fold Layout) */}
      <main className="flex-1 p-3.5 sm:p-5 max-w-[1700px] w-full mx-auto space-y-4">
        {/* Top Status / KPI Counter Strip */}
        <KPICards
          activeEventsCount={summary?.active_events_count ?? activeAlerts.length}
          criticalEventsCount={summary?.critical_events_count ?? 0}
          highRiskCount={summary?.high_risk_count ?? 0}
          moderateRiskCount={summary?.moderate_risk_count ?? 0}
          totalLocations={summary?.total_monitored_locations ?? locations.length}
          highestRiskScore={summary?.highest_risk_score ?? 0.0}
          highestRiskLevel={summary?.highest_risk_level ?? "LOW"}
        />

        {/* Primary Operational Area: GIS Map (Left) + Priority Locations (Right) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
          {/* Left Column (7 cols): NER GIS Landslide Map */}
          <div className="lg:col-span-7 space-y-2">
            <div className="flex items-center justify-between text-xs font-mono px-1">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-zinc-300 font-bold uppercase tracking-wider">
                  NER Landslide Decision Heatmap
                </span>
              </div>
              {selectedLocation && (
                <button
                  onClick={() => handleOpenStation360(selectedLocation.id)}
                  className="text-emerald-400 hover:text-emerald-300 flex items-center gap-1 font-bold transition text-[11px]"
                >
                  <span>Investigate {selectedLocation.name}</span>
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Interactive Leaflet Risk Map */}
            <div className="relative">
              <RiskMap
                locations={locations}
                selectedLocationId={selectedLocationId}
                onSelectLocation={(id) => setSelectedLocationId(id)}
                onOpenInvestigate={handleOpenStation360}
              />
            </div>
          </div>

          {/* Right Column (5 cols): Top Priority Locations */}
          <div className="lg:col-span-5 space-y-2">
            <div className="flex items-center justify-between text-xs font-mono px-1">
              <span className="text-zinc-400 font-bold uppercase tracking-wider">
                High-Risk Sectors &amp; Priority Queue
              </span>
              <Link
                href="/stations"
                className="text-zinc-400 hover:text-white flex items-center gap-1 transition text-[11px]"
              >
                <span>All Stations</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <LocationPriorityTable
              locations={locations}
              selectedLocationId={selectedLocationId}
              onSelectLocation={(id) => setSelectedLocationId(id)}
              onOpenInvestigate={handleOpenStation360}
            />
          </div>
        </div>

        {/* 3. Below Map: Critical Alerts & Active Warning Strip */}
        <div className="bg-zinc-950 border border-zinc-800 rounded p-3.5 space-y-2.5 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-zinc-850 pb-2">
            <div className="flex items-center gap-2">
              <AlertTriangle className={`w-4 h-4 ${activeAlerts.length > 0 ? "text-amber-400" : "text-emerald-400"}`} />
              <span className="text-zinc-200 font-bold uppercase tracking-wider">
                Active Regional Alerts ({activeAlerts.length})
              </span>
            </div>
            <Link
              href="/events"
              className="text-xs text-zinc-400 hover:text-white flex items-center gap-1 font-bold transition"
            >
              <span>Manage Events Queue</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {activeAlerts.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
              {activeAlerts.slice(0, 3).map((ev) => {
                const isCrit = ev.severity === "CRITICAL";
                return (
                  <div
                    key={ev.id}
                    className={`p-3 rounded border flex flex-col justify-between space-y-2 ${
                      isCrit ? "bg-red-950/30 border-red-800/60" : "bg-black border-zinc-800"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-1.5 mb-1">
                          <span
                            className={`text-[9px] font-black px-1.5 py-0.5 rounded uppercase border ${
                              isCrit
                                ? "bg-red-950 text-red-300 border-red-700"
                                : "bg-amber-950 text-amber-300 border-amber-700"
                            }`}
                          >
                            {ev.severity}
                          </span>
                          <span className="text-[10px] text-zinc-400 font-bold">{ev.location_id}</span>
                        </div>
                        <h4 className="font-bold text-white text-xs leading-snug">{ev.summary || ev.event_type?.replace(/_/g, " ")}</h4>
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-zinc-400 pt-1 border-t border-zinc-850">
                      <span>Score: <strong className="text-white">{ev.risk_score.toFixed(1)}</strong></span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleAcknowledgeEvent(ev.id)}
                          disabled={acknowledgingId === ev.id}
                          className="text-zinc-300 hover:text-white underline cursor-pointer disabled:opacity-50"
                        >
                          {acknowledgingId === ev.id ? "Saving..." : "Acknowledge"}
                        </button>
                        <button
                          onClick={() => handleOpenStation360(ev.location_id)}
                          className="text-emerald-400 hover:text-emerald-300 font-bold flex items-center gap-0.5"
                        >
                          <span>Inspect</span>
                          <ChevronRight className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-4 bg-black rounded border border-zinc-850 flex items-center justify-between text-zinc-400">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-zinc-300">All NER sectors operating within safe baseline thresholds. No active alerts requiring immediate intervention.</span>
              </div>
              <Link href="/events" className="text-emerald-400 hover:underline font-bold text-[11px]">
                View Historical Log
              </Link>
            </div>
          )}
        </div>
      </main>

      {/* Understated Footer */}
      <footer className="border-t border-zinc-900 px-5 py-2.5 text-center text-[10px] text-zinc-500 font-mono flex items-center justify-between max-w-[1700px] w-full mx-auto">
        <span>DISASTRA &bull; Disaster Intelligence Command Center &bull; NER India</span>
        <div className="flex items-center gap-4 text-zinc-400">
          <Link href="/system" className="hover:text-white transition">System Health</Link>
          <Link href="/broadcast" className="hover:text-white transition">Broadcast Console</Link>
          <Link href="/field" className="hover:text-white transition">Field Operations</Link>
        </div>
      </footer>
    </div>
  );
}
