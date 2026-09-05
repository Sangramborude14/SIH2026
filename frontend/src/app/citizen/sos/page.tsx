"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  AlertOctagon,
  MapPin,
  Phone,
  Users,
  CheckCircle2,
  Clock,
  Send,
  Navigation,
  ShieldAlert,
  WifiOff,
  RefreshCw,
  Info,
} from "lucide-react";
import { queueOfflineSOS, getPendingSOS } from "@/lib/citizenOfflineStorage";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SOSResponse {
  id: string;
  emergency_type: string;
  status: string; // SENT, RECEIVED, ASSIGNED, RESCUE_EN_ROUTE, RESOLVED
  latitude: number;
  longitude: number;
  location_accuracy?: number;
  location_name?: string;
  contact_name?: string;
  contact_phone?: string;
  num_people: number;
  message?: string;
  assigned_unit?: string;
  responder_notes?: string;
  created_at: string;
  updated_at: string;
}

const EMERGENCY_TYPES = [
  { id: "TRAPPED_BY_LANDSLIDE", label: "Trapped by Landslide", icon: "🧗", desc: "Blocked inside building or under debris" },
  { id: "ROAD_BLOCKED_STRANDED", label: "Road Blocked / Stranded", icon: "🚗", desc: "Cut off on hillside road or vehicle" },
  { id: "MEDICAL_EMERGENCY", label: "Medical Emergency", icon: "🏥", desc: "Severe injury, bleeding, or trauma" },
  { id: "EVACUATION_NEEDED", label: "Evacuation Assistance", icon: "🚶", desc: "Unstable slope threatening residence" },
  { id: "SHELTER_NEEDED", label: "Shelter Needed", icon: "🏠", desc: "House structurally damaged or collapsed" },
];

export default function CitizenSOSPage() {
  const [selectedType, setSelectedType] = useState<string>("TRAPPED_BY_LANDSLIDE");
  const [coords, setCoords] = useState<{ lat: number; lon: number; acc?: number } | null>(null);
  const [locStatus, setLocStatus] = useState<string>("Locating device via GPS...");
  const [landmark, setLandmark] = useState<string>("");
  const [contactName, setContactName] = useState<string>("");
  const [contactPhone, setContactPhone] = useState<string>("");
  const [numPeople, setNumPeople] = useState<number>(1);
  const [message, setMessage] = useState<string>("");
  
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [activeSOS, setActiveSOS] = useState<SOSResponse | null>(null);
  const [isOfflinePending, setIsOfflinePending] = useState<boolean>(false);
  const [offlineItemId, setOfflineItemId] = useState<string | null>(null);

  // Auto-capture GPS
  const captureGPS = useCallback(() => {
    if (typeof window !== "undefined" && "geolocation" in navigator) {
      setLocStatus("Acquiring high-accuracy GPS coordinates...");
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setCoords({
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            acc: pos.coords.accuracy ? Math.round(pos.coords.accuracy) : undefined,
          });
          setLocStatus(`GPS Acquired (±${Math.round(pos.coords.accuracy || 10)}m accuracy)`);
        },
        (err) => {
          setLocStatus("GPS unavailable. Please enter landmark description.");
          // Default fallback coordinates (Gangtok)
          setCoords({ lat: 27.3389, lon: 88.6065 });
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      );
    } else {
      setLocStatus("Location unsupported on this device.");
    }
  }, []);

  useEffect(() => {
    captureGPS();

    // Check if there's already an active or offline SOS stored
    const pendingList = getPendingSOS();
    if (pendingList.length > 0) {
      const topPending = pendingList[pendingList.length - 1];
      setIsOfflinePending(true);
      setOfflineItemId(topPending.id);
    }
  }, [captureGPS]);

  // Poll active SOS status progression if active
  useEffect(() => {
    if (!activeSOS || activeSOS.status === "RESOLVED") return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/citizen/sos/${activeSOS.id}`);
        if (res.ok) {
          const updated: SOSResponse = await res.json();
          setActiveSOS(updated);
        }
      } catch (err) {
        console.warn("Could not poll SOS status", err);
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [activeSOS]);

  const handleSubmitSOS = async () => {
    setSubmitting(true);
    const targetLat = coords?.lat || 27.3389;
    const targetLon = coords?.lon || 88.6065;

    const payload = {
      emergency_type: selectedType,
      latitude: targetLat,
      longitude: targetLon,
      location_accuracy: coords?.acc,
      location_name: landmark.trim() || "Captured GPS Coordinates",
      contact_name: contactName.trim() || undefined,
      contact_phone: contactPhone.trim() || undefined,
      num_people: numPeople,
      message: message.trim() || undefined,
      device_fingerprint: typeof window !== "undefined" ? window.navigator.userAgent : "PWA-CLIENT",
    };

    // If offline or network fails, queue with honest "PENDING — WAITING FOR NETWORK"
    if (typeof window !== "undefined" && !navigator.onLine) {
      const offlineItem = queueOfflineSOS(payload);
      setIsOfflinePending(true);
      setOfflineItemId(offlineItem.id);
      setSubmitting(false);
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/v1/citizen/sos`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data: SOSResponse = await res.json();
        setActiveSOS(data);
        setIsOfflinePending(false);
      } else {
        throw new Error("Server error dispatching SOS");
      }
    } catch (err) {
      console.warn("Network request failed, queueing offline:", err);
      const offlineItem = queueOfflineSOS(payload);
      setIsOfflinePending(true);
      setOfflineItemId(offlineItem.id);
    } finally {
      setSubmitting(false);
    }
  };

  // Stepper Progression Mapping
  const STEPS = [
    { key: "SENT", label: "Dispatched" },
    { key: "RECEIVED", label: "Command Notified" },
    { key: "ASSIGNED", label: "Unit Assigned" },
    { key: "RESCUE_EN_ROUTE", label: "Rescue En Route" },
    { key: "RESOLVED", label: "Resolved" },
  ];

  const getStepIndex = (status: string) => {
    switch (status) {
      case "SENT": return 0;
      case "RECEIVED": return 1;
      case "ASSIGNED": return 2;
      case "RESCUE_EN_ROUTE": return 3;
      case "RESOLVED": return 4;
      default: return 1;
    }
  };

  return (
    <div className="p-4 space-y-4">
      {/* 1. Direct Emergency Call Banner */}
      <div className="bg-red-950/80 border-2 border-red-600 rounded-2xl p-4 flex items-center justify-between shadow-xl shadow-red-950/50">
        <div>
          <div className="text-[10px] font-mono font-black uppercase text-red-300">
            LIFE-THREATENING EMERGENCY
          </div>
          <div className="text-sm font-black text-white">Call 112 Directly</div>
          <div className="text-[11px] text-red-200">Voice dispatch is always fastest</div>
        </div>
        <a
          href="tel:112"
          className="bg-red-600 hover:bg-red-500 text-white font-black text-sm px-4 py-2.5 rounded-xl shadow-lg flex items-center gap-1.5 active:scale-95 transition"
        >
          <Phone className="w-4 h-4" />
          <span>CALL 112</span>
        </a>
      </div>

      {/* 2. ACTIVE SOS TRACKER / OFFLINE PENDING STATE */}
      {isOfflinePending && (
        <div className="bg-amber-950/90 border-2 border-amber-600 rounded-3xl p-5 shadow-2xl space-y-3 animate-pulse">
          <div className="flex items-center gap-2.5 text-amber-300">
            <WifiOff className="w-6 h-6 text-amber-400 flex-shrink-0" />
            <div>
              <div className="text-[10px] font-mono font-bold uppercase tracking-wider">
                TRANSPARENT OFFLINE STATUS
              </div>
              <h3 className="text-base font-black uppercase text-white">
                PENDING — WAITING FOR NETWORK
              </h3>
            </div>
          </div>
          <p className="text-xs text-amber-200 leading-relaxed">
            Your emergency distress beacon is safely recorded on this phone ({offlineItemId}). As soon as your device reconnects to cell reception or Wi-Fi, it will transmit automatically to District Disaster Command.
          </p>
          <div className="pt-2 border-t border-amber-800/80 flex items-center justify-between text-xs text-amber-300">
            <span>Keep this app open or phone on.</span>
            <a href="tel:112" className="underline font-bold text-white">
              Try Calling 112
            </a>
          </div>
        </div>
      )}

      {activeSOS && !isOfflinePending && (
        <div className="bg-slate-900 border-2 border-red-600 rounded-3xl p-5 shadow-2xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-red-600/30 flex items-center justify-center text-red-400">
                <AlertOctagon className="w-5 h-5 animate-pulse" />
              </div>
              <div>
                <div className="text-[10px] font-mono font-bold text-red-400 uppercase">
                  ACTIVE RESCUE BEACON
                </div>
                <div className="text-xs font-mono text-slate-300">ID: {activeSOS.id.substring(0, 8)}</div>
              </div>
            </div>
            <span className="text-[10px] font-mono font-bold bg-red-950 text-red-300 px-2.5 py-1 rounded-full border border-red-800 uppercase">
              {activeSOS.status.replace(/_/g, " ")}
            </span>
          </div>

          {/* Stepper Progress */}
          <div className="space-y-1.5">
            <div className="text-[10px] font-mono text-slate-400 uppercase font-bold">
              Rescue Progression Status:
            </div>
            <div className="grid grid-cols-5 gap-1 pt-1">
              {STEPS.map((step, idx) => {
                const currentIdx = getStepIndex(activeSOS.status);
                const isPassed = idx <= currentIdx;
                return (
                  <div key={step.key} className="flex flex-col items-center gap-1 text-center">
                    <div
                      className={`w-full h-1.5 rounded-full ${
                        isPassed ? "bg-red-500" : "bg-slate-800"
                      }`}
                    />
                    <span
                      className={`text-[9px] font-mono leading-tight ${
                        idx === currentIdx
                          ? "text-red-400 font-bold"
                          : isPassed
                          ? "text-slate-300"
                          : "text-slate-600"
                      }`}
                    >
                      {step.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {activeSOS.assigned_unit && (
            <div className="p-2.5 bg-slate-950 rounded-xl border border-slate-800 text-xs font-mono">
              <span className="text-slate-400">Assigned Unit: </span>
              <span className="text-emerald-400 font-bold">{activeSOS.assigned_unit}</span>
            </div>
          )}

          {activeSOS.responder_notes && (
            <div className="p-2.5 bg-slate-950 rounded-xl border border-slate-800 text-xs">
              <span className="text-slate-400 font-mono text-[10px] uppercase block">
                Responder Advisory:
              </span>
              <span className="text-slate-200 mt-0.5 block">{activeSOS.responder_notes}</span>
            </div>
          )}

          <div className="text-center text-[10px] font-mono text-slate-500">
            Auto-refreshing status every 10 seconds • Stay in a safe, visible position
          </div>
        </div>
      )}

      {/* 3. SOS DISPATCH FORM (Shown if not currently tracking) */}
      {!activeSOS && (
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-5 space-y-4">
          <div>
            <h2 className="text-base font-black text-slate-100 flex items-center gap-2 uppercase tracking-wide">
              <AlertOctagon className="w-5 h-5 text-red-500" />
              Dispatch Emergency SOS
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Select your emergency category and tap submit. Rescue units and District Disaster Control will receive your GPS coordinates.
            </p>
          </div>

          {/* Emergency Type Selector */}
          <div className="space-y-2">
            <label className="text-[10px] font-mono uppercase font-bold text-slate-400">
              1. What is the Emergency?
            </label>
            <div className="grid grid-cols-1 gap-2">
              {EMERGENCY_TYPES.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setSelectedType(t.id)}
                  className={`p-3 rounded-2xl border text-left flex items-center gap-3 transition active:scale-[0.99] ${
                    selectedType === t.id
                      ? "bg-red-950/60 border-red-500 text-white shadow-md shadow-red-950/40"
                      : "bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700"
                  }`}
                >
                  <span className="text-xl">{t.icon}</span>
                  <div className="flex-1">
                    <div className="text-xs font-bold">{t.label}</div>
                    <div className="text-[10px] text-slate-400">{t.desc}</div>
                  </div>
                  <div
                    className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                      selectedType === t.id
                        ? "border-red-400 bg-red-500 text-white"
                        : "border-slate-700"
                    }`}
                  >
                    {selectedType === t.id && <div className="w-2 h-2 rounded-full bg-white" />}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* GPS Location Readout */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 font-bold uppercase">
              <span>2. Your GPS Location</span>
              <button
                type="button"
                onClick={captureGPS}
                className="text-red-400 hover:text-red-300 flex items-center gap-0.5"
              >
                <RefreshCw className="w-2.5 h-2.5" /> Re-check
              </button>
            </div>
            <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl text-xs font-mono flex items-start gap-2">
              <MapPin className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <div className="text-slate-200 font-bold">
                  {coords ? `${coords.lat.toFixed(4)}°N, ${coords.lon.toFixed(4)}°E` : "Locating..."}
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">{locStatus}</div>
              </div>
            </div>
          </div>

          {/* Landmark Description Input */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase font-bold text-slate-400">
              Landmark / Visible Description (Optional but Helpful)
            </label>
            <input
              type="text"
              value={landmark}
              onChange={(e) => setLandmark(e.target.value)}
              placeholder="e.g. Near Tathangchen School, white Maruti car, red tin roof house"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-red-500"
            />
          </div>

          {/* People Count & Phone */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-[10px] font-mono uppercase font-bold text-slate-400">
                People in Danger
              </label>
              <div className="flex items-center bg-slate-950 border border-slate-800 rounded-xl p-1 justify-between">
                <button
                  type="button"
                  onClick={() => setNumPeople(Math.max(1, numPeople - 1))}
                  className="w-8 h-8 rounded-lg bg-slate-800 text-slate-200 font-bold flex items-center justify-center hover:bg-slate-700"
                >
                  -
                </button>
                <span className="text-sm font-bold font-mono text-white">{numPeople}</span>
                <button
                  type="button"
                  onClick={() => setNumPeople(numPeople + 1)}
                  className="w-8 h-8 rounded-lg bg-slate-800 text-slate-200 font-bold flex items-center justify-center hover:bg-slate-700"
                >
                  +
                </button>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-mono uppercase font-bold text-slate-400">
                Contact Phone
              </label>
              <input
                type="tel"
                value={contactPhone}
                onChange={(e) => setContactPhone(e.target.value)}
                placeholder="+91..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-red-500 font-mono h-10"
              />
            </div>
          </div>

          {/* Situation Message */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase font-bold text-slate-400">
              Brief Message / Trapped Details
            </label>
            <textarea
              rows={2}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="e.g. Mud came down slope, 2 elderly individuals cannot walk, water rising"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-red-500"
            />
          </div>

          {/* Giant Submit Button */}
          <button
            type="button"
            onClick={handleSubmitSOS}
            disabled={submitting}
            className="w-full py-4 bg-gradient-to-r from-red-600 via-rose-600 to-red-700 hover:from-red-500 hover:to-red-600 text-white font-black text-base uppercase tracking-wider rounded-2xl shadow-xl shadow-red-950/70 active:scale-[0.98] transition flex items-center justify-center gap-2"
          >
            {submitting ? (
              <>
                <RefreshCw className="w-5 h-5 animate-spin" />
                <span>Transmitting Beacon...</span>
              </>
            ) : (
              <>
                <Send className="w-5 h-5" />
                <span>SEND RESCUE SOS BEACON</span>
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
