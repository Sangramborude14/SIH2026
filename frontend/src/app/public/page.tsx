"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Shield,
  AlertTriangle,
  AlertOctagon,
  CheckCircle2,
  Navigation,
  Compass,
  MapPin,
  Phone,
  Radio,
  Clock,
  Info,
  ChevronRight,
  RefreshCw,
  ExternalLink,
  LifeBuoy,
  Bell,
  BellOff,
  Eye,
} from "lucide-react";
import Link from "next/link";
import PublicSafetyMap from "@/components/public/PublicSafetyMap";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SafetyGuidanceItem {
  category: string; // DO, DONT, NOTICE
  title: string;
  instruction: string;
}

interface SafetyPointItem {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  point_type: string;
  capacity?: number | null;
  availability: string;
  source: string;
  contact_number?: string | null;
  distance_km?: number | null;
  is_simulated: boolean;
}

interface PublicAlertItem {
  alert_id: string;
  event_id: string;
  location_id: string;
  location_name: string;
  district: string;
  state: string;
  hazard_type: string;
  public_status: string; // NO_ALERT, MONITORING, ALERT, URGENT
  message_title: string;
  message_summary: string;
  affected_radius_km: number;
  detected_at: string;
  updated_at: string;
  data_mode: string;
}

interface PublicRiskResponse {
  is_affected: boolean;
  public_status: string;
  user_zone: string;
  location_name: string;
  nearest_hazard_km?: number | null;
  active_alert?: PublicAlertItem | null;
  guidance: SafetyGuidanceItem[];
  nearest_safe_point?: SafetyPointItem | null;
  data_mode: string;
  timestamp: string;
}

export default function PublicDisasterAlertPage() {
  const [selectedStationId, setSelectedStationId] = useState<string>("NER-SIK-GANGTOK-01");
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [geoStatus, setGeoStatus] = useState<string>("Locating device...");
  const [riskData, setRiskData] = useState<PublicRiskResponse | null>(null);
  const [safetyPoints, setSafetyPoints] = useState<SafetyPointItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [acknowledged, setAcknowledged] = useState<boolean>(false);
  const [isSyncingAck, setIsSyncingAck] = useState<boolean>(false);
  const [lastCheckedTime, setLastCheckedTime] = useState<string | null>(null);

  // GPS Geolocation
  useEffect(() => {
    if (typeof window !== "undefined" && "geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude });
          setGeoStatus("GPS Acquired");
        },
        (err) => {
          setGeoStatus("GPS Denied (Using Station Sector)");
          setCoords({ lat: 27.3389, lon: 88.6065 });
        },
        { enableHighAccuracy: true, timeout: 8000 }
      );
    } else {
      setGeoStatus("Location Unsupported");
    }
  }, []);

  // Fetch Public Risk Evaluation
  const evaluateRisk = useCallback(async () => {
    try {
      setLoading(true);
      const url = coords
        ? `${API_URL}/api/v1/public/risk?latitude=${coords.lat}&longitude=${coords.lon}`
        : `${API_URL}/api/v1/public/risk?location_id=${selectedStationId}`;

      const res = await fetch(url);
      if (res.ok) {
        const data: PublicRiskResponse = await res.json();
        setRiskData(data);

        // Fetch Safety Points for sector
        const ptsRes = await fetch(`${API_URL}/api/v1/public/safety-points`);
        if (ptsRes.ok) {
          const pts: SafetyPointItem[] = await ptsRes.json();
          setSafetyPoints(pts);
        }

        const now = new Date();
        setLastCheckedTime(
          `${now.getHours().toString().padStart(2, "0")}:${now
            .getMinutes()
            .toString()
            .padStart(2, "0")}`
        );
      }
    } catch (err) {
      console.error("Public risk check error:", err);
    } finally {
      setLoading(false);
    }
  }, [coords, selectedStationId]);

  useEffect(() => {
    evaluateRisk();
    const interval = setInterval(evaluateRisk, 20000); // 20s public sync
    return () => clearInterval(interval);
  }, [evaluateRisk]);

  // Acknowledge Alert View
  const handleAcknowledge = async () => {
    if (!riskData?.active_alert) return;
    setIsSyncingAck(true);
    try {
      await fetch(`${API_URL}/api/v1/public/acknowledge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_id: riskData.active_alert.event_id,
          location_id: riskData.active_alert.location_id,
          user_id: "CITIZEN_PUBLIC_USER",
        }),
      });
      setAcknowledged(true);
    } catch (err) {
      console.error("Acknowledgment error", err);
    } finally {
      setIsSyncingAck(false);
    }
  };

  const isUrgent = riskData?.public_status === "URGENT";
  const isAlert = riskData?.public_status === "ALERT";
  const isMonitoring = riskData?.public_status === "MONITORING";

  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100 font-sans flex flex-col max-w-md sm:max-w-xl mx-auto shadow-2xl border-x border-slate-800">
      {/* 1. Public Safety Header */}
      <header className="bg-slate-900 border-b border-slate-800 px-4 py-3 sticky top-0 z-40 shadow-md">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div
              className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                isUrgent
                  ? "bg-red-600/20 border border-red-500/40 text-red-400"
                  : isAlert
                  ? "bg-orange-600/20 border border-orange-500/40 text-orange-400"
                  : "bg-emerald-600/20 border border-emerald-500/40 text-emerald-400"
              }`}
            >
              <Shield className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[10px] font-mono tracking-wider uppercase text-slate-400 font-bold flex items-center gap-1.5">
                <span>PUBLIC DISASTER SAFETY</span>
                <span>•</span>
                <span>{geoStatus}</span>
              </div>
              <h1 className="text-sm font-bold text-slate-100">
                {riskData?.location_name || "North Eastern Region"}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/citizen"
              className="text-[11px] font-mono bg-red-950/80 hover:bg-red-900/90 text-red-300 font-bold px-2.5 py-1.5 rounded-lg border border-red-800 flex items-center gap-1 transition"
            >
              <Shield className="w-3.5 h-3.5 text-red-400" />
              <span>Citizen SOS App</span>
            </Link>
            <Link
              href="/public/alerts"
              className="text-[11px] font-mono bg-slate-950 hover:bg-slate-800 text-indigo-300 px-2.5 py-1.5 rounded-lg border border-slate-800 flex items-center gap-1 transition"
            >
              <Bell className="w-3.5 h-3.5 text-indigo-400" />
              <span>All Alerts</span>
            </Link>
          </div>
        </div>

        {/* Location / Sector Manual Override Selector */}
        <div className="mt-2.5 flex items-center justify-between gap-2 text-xs font-mono">
          <span className="text-[10px] text-slate-400 uppercase">Sector:</span>
          <select
            value={selectedStationId}
            onChange={(e) => setSelectedStationId(e.target.value)}
            className="flex-1 bg-slate-950 border border-slate-800 rounded p-1 text-slate-300 text-[11px] focus:outline-none"
          >
            <option value="NER-SIK-GANGTOK-01">Gangtok Municipal Ridge (Sikkim)</option>
            <option value="NER-MIZ-AIZAWL-01">Aizawl Chite Valley (Mizoram)</option>
            <option value="NER-NAG-KOHIMA-01">Kohima-Dzülake Corridor (Nagaland)</option>
            <option value="NER-MEG-SHILLONG-01">Shillong Peak Sector (Meghalaya)</option>
            <option value="NER-ARU-ITANAGAR-01">Itanagar Hills (Arunachal)</option>
            <option value="NER-ASM-HAFLONG-01">Haflong Hill Station (Assam)</option>
          </select>
        </div>
      </header>

      {/* 2. Main Public Safety Body */}
      <main className="flex-1 p-3.5 sm:p-4 space-y-4 overflow-y-auto">
        {/* PROVENANCE / SIMULATION BANNER */}
        <div
          className={`p-2.5 rounded-xl border text-xs font-mono flex items-center justify-between ${
            riskData?.data_mode === "SIMULATION"
              ? "bg-amber-950/40 border-amber-800/80 text-amber-300"
              : "bg-slate-900 border-slate-800 text-slate-400"
          }`}
        >
          <div className="flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5 flex-shrink-0" />
            <span className="font-bold uppercase">
              {riskData?.data_mode === "SIMULATION"
                ? "DEMO / SIMULATION MODE"
                : "OPERATING UNDER LIVE ENVIRONMENTAL SENSORS"}
            </span>
          </div>
          <span className="text-[10px] text-slate-500">Sync: {lastCheckedTime || "Just now"}</span>
        </div>

        {/* PRIMARY PUBLIC ALERT BANNER: Answers "Am I Affected?" & "How Serious Is It?" */}
        <div
          className={`rounded-2xl border p-5 space-y-3 shadow-xl ${
            isUrgent
              ? "bg-red-950/80 border-red-700 text-red-100 shadow-red-950/50"
              : isAlert
              ? "bg-orange-950/80 border-orange-700 text-orange-100 shadow-orange-950/50"
              : isMonitoring
              ? "bg-yellow-950/60 border-yellow-800/80 text-yellow-100"
              : "bg-slate-900 border-emerald-900/60 text-emerald-100"
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {isUrgent ? (
                <AlertOctagon className="w-6 h-6 text-red-400 animate-bounce" />
              ) : isAlert ? (
                <AlertTriangle className="w-6 h-6 text-orange-400" />
              ) : (
                <CheckCircle2 className="w-6 h-6 text-emerald-400" />
              )}
              <span className="text-xl font-black font-mono tracking-wider uppercase">
                {riskData?.public_status === "URGENT"
                  ? "URGENT WARNING"
                  : riskData?.public_status === "ALERT"
                  ? "HAZARD ALERT"
                  : riskData?.public_status === "MONITORING"
                  ? "WEATHER MONITORING"
                  : "NO CURRENT ALERT"}
              </span>
            </div>

            <span className="text-[10px] font-mono font-bold bg-black/40 px-2.5 py-1 rounded-full uppercase">
              Zone: {riskData?.user_zone.replace(/_/g, " ")}
            </span>
          </div>

          <div>
            <h2 className="text-sm font-bold leading-snug">
              {riskData?.active_alert?.message_title ||
                "Landslide conditions are currently stable in your monitored sector."}
            </h2>
            <p className="text-xs text-slate-300 mt-1 leading-relaxed">
              {riskData?.active_alert?.message_summary ||
                "No immediate landslide danger detected. Environmental moisture and slope stability remain within normal thresholds."}
            </p>
          </div>

          {/* Acknowledgment Action */}
          {(isUrgent || isAlert) && (
            <div className="pt-2 border-t border-white/10 flex items-center justify-between gap-3">
              <span className="text-[10px] font-mono text-slate-300">
                {acknowledged
                  ? "✓ Safety guidance acknowledged"
                  : "Please review the safety steps below:"}
              </span>
              <button
                onClick={handleAcknowledge}
                disabled={acknowledged || isSyncingAck}
                className={`text-xs font-mono font-bold px-3 py-1.5 rounded-lg transition ${
                  acknowledged
                    ? "bg-emerald-700 text-white cursor-default"
                    : "bg-white text-slate-950 hover:bg-slate-200 active:bg-slate-300 shadow-md"
                }`}
              >
                {acknowledged
                  ? "ACKNOWLEDGED"
                  : isSyncingAck
                  ? "Syncing..."
                  : "I UNDERSTAND"}
              </button>
            </div>
          )}
        </div>

        {/* PUBLIC SAFETY MAP: Shows User GPS, Danger Zone, and Nearest Safer Reference Points */}
        <PublicSafetyMap
          userCoords={coords}
          locationName={riskData?.location_name || "Assigned Sector"}
          hazardSeverity={riskData?.public_status || "NO_ALERT"}
          affectedRadiusKm={riskData?.active_alert?.affected_radius_km ?? 15.0}
          safetyPoints={safetyPoints}
        />

        {/* STRUCTURED SAFETY GUIDANCE: Answers "What should I do?" */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <h3 className="text-xs font-bold font-mono uppercase text-slate-200 flex items-center gap-1.5">
              <Compass className="w-4 h-4 text-indigo-400" />
              What You Should Do (Safety Checklist)
            </h3>
            <span className="text-[10px] font-mono text-slate-500">Official Conservative Guidance</span>
          </div>

          <div className="space-y-2.5">
            {riskData?.guidance && riskData.guidance.length > 0 ? (
              riskData.guidance.map((item, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded-xl border space-y-1 text-xs ${
                    item.category === "DO"
                      ? "bg-emerald-950/30 border-emerald-900/60"
                      : item.category === "DONT"
                      ? "bg-red-950/30 border-red-900/60"
                      : "bg-slate-950 border-slate-800"
                  }`}
                >
                  <div className="flex items-center gap-2 font-mono text-[11px] font-bold">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] ${
                        item.category === "DO"
                          ? "bg-emerald-600 text-white"
                          : item.category === "DONT"
                          ? "bg-red-600 text-white"
                          : "bg-slate-700 text-slate-200"
                      }`}
                    >
                      {item.category}
                    </span>
                    <span className="text-slate-100">{item.title}</span>
                  </div>
                  <p className="text-slate-300 text-[11px] leading-relaxed pl-1">
                    {item.instruction}
                  </p>
                </div>
              ))
            ) : (
              <div className="text-center py-3 text-slate-500 text-xs font-mono">
                Loading safety checklist...
              </div>
            )}
          </div>
        </div>

        {/* EMERGENCY CONTACTS STRIP */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-2.5">
          <div className="text-xs font-bold font-mono uppercase text-slate-200 flex items-center gap-1.5">
            <Phone className="w-4 h-4 text-red-400" />
            Verified Emergency Assistance Helplines
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800 flex justify-between items-center">
              <span className="text-slate-400">National Emergency:</span>
              <a href="tel:112" className="font-bold text-red-400 hover:underline">
                112
              </a>
            </div>

            <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800 flex justify-between items-center">
              <span className="text-slate-400">Disaster Helpline:</span>
              <a href="tel:1070" className="font-bold text-indigo-400 hover:underline">
                1070
              </a>
            </div>

            <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800 flex justify-between items-center">
              <span className="text-slate-400">Ambulance:</span>
              <a href="tel:108" className="font-bold text-emerald-400 hover:underline">
                108
              </a>
            </div>

            <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800 flex justify-between items-center">
              <span className="text-slate-400">State Control:</span>
              <span className="font-bold text-slate-200">03592-202461</span>
            </div>
          </div>
        </div>
      </main>

      {/* 3. Public Footer */}
      <footer className="border-t border-slate-800/80 px-4 py-3 bg-slate-950 text-center text-[10px] font-mono text-slate-500 space-y-1">
        <div>DISASTRA Early Warning System • Public Citizen Advisory Portal</div>
        <div className="text-slate-600">Follow official instructions from district disaster management authorities.</div>
      </footer>
    </div>
  );
}
