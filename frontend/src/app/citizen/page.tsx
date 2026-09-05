"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Shield,
  AlertTriangle,
  AlertOctagon,
  CheckCircle2,
  Phone,
  Camera,
  MapPin,
  TrendingUp,
  Minus,
  TrendingDown,
  Navigation,
  ExternalLink,
  ChevronRight,
  Info,
  Clock,
  Compass,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ImmediateGuidanceItem {
  category: string;
  instruction: string;
}

interface NearestShelterInfo {
  name: string;
  distance_km?: number | null;
  capacity?: number | null;
  availability: string;
  contact_number?: string | null;
  latitude: number;
  longitude: number;
}

interface CitizenRiskStatusResponse {
  safety_level: string; // LOW, MODERATE, HIGH, CRITICAL
  safety_color: string; // green, yellow, orange, red
  safety_headline: string;
  safety_summary: string;
  trend_24h: string; // INCREASING, STABLE, DECREASING
  trend_description: string;
  location_name: string;
  nearest_hazard_km?: number | null;
  action_recommendation: string;
  immediate_dos_donts: ImmediateGuidanceItem[];
  nearest_shelter?: NearestShelterInfo | null;
  emergency_contacts: Record<string, string>;
  timestamp: string;
  data_mode: string;
}

export default function CitizenHomePage() {
  const [selectedSector, setSelectedSector] = useState<string>("NER-SIK-GANGTOK-01");
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [gpsStatus, setGpsStatus] = useState<string>("Detecting GPS...");
  const [riskData, setRiskData] = useState<CitizenRiskStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [lastCheckTime, setLastCheckTime] = useState<string>("");

  // Acquire Geolocation
  const requestGPS = useCallback(() => {
    if (typeof window !== "undefined" && "geolocation" in navigator) {
      setGpsStatus("Acquiring GPS...");
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude });
          setGpsStatus("GPS Live");
        },
        (err) => {
          setGpsStatus("GPS Inactive (Using Sector)");
          setCoords(null);
        },
        { enableHighAccuracy: true, timeout: 7000 }
      );
    } else {
      setGpsStatus("GPS Unsupported");
    }
  }, []);

  useEffect(() => {
    requestGPS();
  }, [requestGPS]);

  // Fetch Citizen Safety Assessment
  const fetchCitizenStatus = useCallback(async () => {
    try {
      setLoading(true);
      const query = coords
        ? `latitude=${coords.lat}&longitude=${coords.lon}`
        : `location_id=${selectedSector}`;

      const res = await fetch(`${API_URL}/api/v1/citizen/risk?${query}`);
      if (res.ok) {
        const data: CitizenRiskStatusResponse = await res.json();
        setRiskData(data);
        const now = new Date();
        setLastCheckTime(
          `${now.getHours().toString().padStart(2, "0")}:${now
            .getMinutes()
            .toString()
            .padStart(2, "0")}`
        );
      }
    } catch (err) {
      console.warn("Failed to fetch citizen status:", err);
    } finally {
      setLoading(false);
    }
  }, [coords, selectedSector]);

  useEffect(() => {
    fetchCitizenStatus();
    const interval = setInterval(fetchCitizenStatus, 30000); // 30s refresh
    return () => clearInterval(interval);
  }, [fetchCitizenStatus]);

  const isCritical = riskData?.safety_level === "CRITICAL";
  const isHigh = riskData?.safety_level === "HIGH";
  const isModerate = riskData?.safety_level === "MODERATE";

  return (
    <div className="p-4 space-y-4">
      {/* 1. Location & Sector Switcher */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3 flex flex-col gap-2">
        <div className="flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-1.5 text-slate-400">
            <MapPin className="w-3.5 h-3.5 text-red-400" />
            <span className="text-[11px] uppercase font-bold">{gpsStatus}</span>
          </div>
          <button
            onClick={requestGPS}
            className="text-[10px] text-red-400 hover:text-red-300 font-bold flex items-center gap-1"
          >
            <Navigation className="w-3 h-3" />
            Use My GPS
          </button>
        </div>

        <select
          value={selectedSector}
          onChange={(e) => {
            setSelectedSector(e.target.value);
            setCoords(null);
            setGpsStatus("Manual Sector Selected");
          }}
          className="bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded-xl p-2.5 focus:outline-none focus:border-red-500 font-medium"
        >
          <option value="NER-SIK-GANGTOK-01">Gangtok Municipal Ridge (Sikkim)</option>
          <option value="NER-MIZ-AIZAWL-01">Aizawl Chite Valley (Mizoram)</option>
          <option value="NER-NAG-KOHIMA-01">Kohima-Dzülake Corridor (Nagaland)</option>
          <option value="NER-MEG-SHILLONG-01">Shillong Peak Corridor (Meghalaya)</option>
          <option value="NER-ARU-ITANAGAR-01">Itanagar Hills (Arunachal Pradesh)</option>
          <option value="NER-ASM-HAFLONG-01">Haflong Hill Station (Assam)</option>
        </select>
      </div>

      {/* 2. QUESTION 1: "Am I Currently Safe?" */}
      <section
        className={`rounded-3xl p-5 border-2 shadow-2xl transition-all ${
          isCritical
            ? "bg-gradient-to-b from-red-950/90 to-red-900/60 border-red-500 shadow-red-950/60 text-white"
            : isHigh
            ? "bg-gradient-to-b from-orange-950/90 to-amber-950/60 border-orange-500 shadow-orange-950/60 text-white"
            : isModerate
            ? "bg-gradient-to-b from-yellow-950/80 to-slate-900 border-yellow-500/80 text-yellow-100"
            : "bg-gradient-to-b from-emerald-950/80 to-slate-900 border-emerald-600/80 text-emerald-100"
        }`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div
              className={`w-12 h-12 rounded-2xl flex items-center justify-center ${
                isCritical
                  ? "bg-red-600 text-white animate-bounce"
                  : isHigh
                  ? "bg-orange-600 text-white"
                  : isModerate
                  ? "bg-yellow-500 text-slate-950"
                  : "bg-emerald-600 text-white"
              }`}
            >
              {isCritical ? (
                <AlertOctagon className="w-7 h-7" />
              ) : isHigh || isModerate ? (
                <AlertTriangle className="w-7 h-7" />
              ) : (
                <CheckCircle2 className="w-7 h-7" />
              )}
            </div>
            <div>
              <div className="text-[11px] font-mono tracking-wider font-extrabold uppercase opacity-80">
                CURRENT SAFETY STATUS
              </div>
              <h2 className="text-xl font-black uppercase tracking-tight">
                {isCritical
                  ? "CRITICAL DANGER"
                  : isHigh
                  ? "HIGH HAZARD"
                  : isModerate
                  ? "MODERATE WATCH"
                  : "SAFE / NORMAL"}
              </h2>
            </div>
          </div>

          <span className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-black/40 border border-white/10">
            {lastCheckTime ? `Updated ${lastCheckTime}` : "Checking..."}
          </span>
        </div>

        <div className="mt-4 pt-3 border-t border-white/15">
          <h3 className="font-bold text-sm leading-snug">
            {riskData?.safety_headline || "Assessing slope stability..."}
          </h3>
          <p className="text-xs mt-1.5 opacity-90 leading-relaxed">
            {riskData?.safety_summary ||
              "Monitoring live rainfall and environmental telemetry across your area."}
          </p>
        </div>

        {riskData?.nearest_hazard_km && (
          <div className="mt-3 inline-flex items-center gap-1.5 text-[11px] font-mono font-bold bg-black/30 px-3 py-1 rounded-lg">
            <MapPin className="w-3.5 h-3.5 text-red-400" />
            <span>Hazard Active {riskData.nearest_hazard_km} km from you</span>
          </div>
        )}
      </section>

      {/* 3. QUESTION 2: "Is Landslide Risk Increasing Near Me?" */}
      <section className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-mono uppercase text-slate-400 font-bold flex items-center gap-1">
            <Clock className="w-3.5 h-3.5 text-indigo-400" />
            24-Hour Risk Trend
          </span>
          <div
            className={`px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold flex items-center gap-1 ${
              riskData?.trend_24h === "INCREASING"
                ? "bg-red-950 text-red-400 border border-red-800"
                : riskData?.trend_24h === "DECREASING"
                ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                : "bg-slate-800 text-slate-300 border border-slate-700"
            }`}
          >
            {riskData?.trend_24h === "INCREASING" ? (
              <>
                <TrendingUp className="w-3.5 h-3.5" />
                <span>INCREASING</span>
              </>
            ) : riskData?.trend_24h === "DECREASING" ? (
              <>
                <TrendingDown className="w-3.5 h-3.5" />
                <span>DECREASING</span>
              </>
            ) : (
              <>
                <Minus className="w-3.5 h-3.5" />
                <span>STABLE</span>
              </>
            )}
          </div>
        </div>

        <p className="text-xs text-slate-300 leading-relaxed font-medium">
          {riskData?.trend_description ||
            "Slope conditions and rainfall patterns are being computed for the next 24 hours."}
        </p>
      </section>

      {/* 4. QUESTION 3: "What Should I Do Right Now?" */}
      <section className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
          <div className="text-xs font-bold font-mono uppercase text-slate-200 flex items-center gap-1.5">
            <Compass className="w-4 h-4 text-indigo-400" />
            Immediate Action Required
          </div>
          <Link
            href="/citizen/safety"
            className="text-[11px] text-red-400 hover:text-red-300 font-bold flex items-center gap-0.5"
          >
            Full Guide <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {/* Priority 1-Sentence Action */}
        <div className="p-3 bg-red-950/30 border border-red-900/60 rounded-xl">
          <div className="text-[10px] font-mono uppercase font-bold text-red-400 mb-1">
            Recommended Action:
          </div>
          <p className="text-xs font-semibold text-slate-100 leading-relaxed">
            {riskData?.action_recommendation ||
              "Maintain situational awareness. Review emergency shelter locations."}
          </p>
        </div>

        {/* Immediate DOs and DONTs */}
        <div className="space-y-2">
          {riskData?.immediate_dos_donts?.map((item, idx) => (
            <div
              key={idx}
              className={`p-2.5 rounded-xl border text-xs flex items-start gap-2 ${
                item.category === "DO"
                  ? "bg-emerald-950/20 border-emerald-900/40 text-emerald-200"
                  : "bg-red-950/20 border-red-900/40 text-red-200"
              }`}
            >
              <span
                className={`text-[9px] font-black font-mono px-1.5 py-0.5 rounded ${
                  item.category === "DO" ? "bg-emerald-600 text-white" : "bg-red-600 text-white"
                }`}
              >
                {item.category}
              </span>
              <span className="text-slate-200 font-medium leading-snug">{item.instruction}</span>
            </div>
          ))}
        </div>
      </section>

      {/* 5. QUESTION 4: "How Do I Request Help or Report Something?" */}
      <section className="grid grid-cols-2 gap-3">
        {/* SOS Button */}
        <Link
          href="/citizen/sos"
          className="p-4 bg-gradient-to-br from-red-700 to-rose-900 rounded-2xl border border-red-500/60 shadow-lg shadow-red-950/50 flex flex-col justify-between active:scale-95 transition"
        >
          <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center text-white mb-2">
            <AlertOctagon className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <div className="text-sm font-black text-white uppercase tracking-wider">Emergency SOS</div>
            <div className="text-[11px] text-red-200 mt-0.5">Send rescue beacon with GPS</div>
          </div>
        </Link>

        {/* Report Hazard Button */}
        <Link
          href="/citizen/report"
          className="p-4 bg-slate-900 border border-slate-700 hover:border-slate-600 rounded-2xl flex flex-col justify-between active:scale-95 transition"
        >
          <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-indigo-400 mb-2">
            <Camera className="w-5 h-5" />
          </div>
          <div>
            <div className="text-sm font-bold text-slate-100">Report Hazard</div>
            <div className="text-[11px] text-slate-400 mt-0.5">Photo of crack, rockfall, or mud</div>
          </div>
        </Link>
      </section>

      {/* 6. Nearest Safe Shelter */}
      {riskData?.nearest_shelter && (
        <section className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase text-slate-400 font-bold flex items-center gap-1">
              <MapPin className="w-3.5 h-3.5 text-emerald-400" />
              Nearest Designated Shelter
            </span>
            <span className="text-[10px] font-mono font-bold bg-emerald-950 text-emerald-400 px-2 py-0.5 rounded border border-emerald-800">
              {riskData.nearest_shelter.availability}
            </span>
          </div>

          <div className="flex items-start justify-between gap-2 pt-1">
            <div>
              <h4 className="text-xs font-bold text-slate-100">
                {riskData.nearest_shelter.name}
              </h4>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Approx. {riskData.nearest_shelter.distance_km} km from your monitored point
              </p>
            </div>
            {riskData.nearest_shelter.contact_number && (
              <a
                href={`tel:${riskData.nearest_shelter.contact_number.split("/")[0].trim()}`}
                className="bg-slate-800 hover:bg-slate-700 text-slate-200 px-2.5 py-1.5 rounded-lg text-xs font-mono flex items-center gap-1 flex-shrink-0"
              >
                <Phone className="w-3 h-3 text-emerald-400" />
                Call
              </a>
            )}
          </div>
        </section>
      )}

      {/* 7. Emergency Helpline Strip */}
      <section className="bg-slate-900 border border-slate-800 rounded-2xl p-3.5">
        <div className="text-[10px] font-mono uppercase text-slate-400 font-bold mb-2 flex items-center gap-1">
          <Phone className="w-3 h-3 text-red-400" />
          Verified Emergency Helplines
        </div>
        <div className="grid grid-cols-2 gap-2">
          <a
            href="tel:112"
            className="bg-slate-950 hover:bg-slate-800 p-2.5 rounded-xl border border-slate-800 flex items-center justify-between transition"
          >
            <span className="text-xs text-slate-300">National Emergency:</span>
            <span className="text-sm font-black text-red-400 font-mono">112</span>
          </a>
          <a
            href="tel:1070"
            className="bg-slate-950 hover:bg-slate-800 p-2.5 rounded-xl border border-slate-800 flex items-center justify-between transition"
          >
            <span className="text-xs text-slate-300">Disaster Helpline:</span>
            <span className="text-sm font-black text-indigo-400 font-mono">1070</span>
          </a>
        </div>
      </section>
    </div>
  );
}
