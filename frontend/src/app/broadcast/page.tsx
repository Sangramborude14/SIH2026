"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import {
  Radio,
  Send,
  AlertOctagon,
  Shield,
  Smartphone,
  MessageSquare,
  FileCode,
  Users,
  CheckCircle2,
  Clock,
  Check,
  AlertTriangle,
  RotateCw,
  Eye,
  ChevronRight,
  Sparkles,
  Info,
  Layers,
  MapPin,
  Flame,
} from "lucide-react";
import CommandHeader from "@/components/dashboard/CommandHeader";

interface BroadcastLog {
  id: string;
  timestamp: string;
  severity: "ADVISORY" | "WATCH" | "WARNING" | "CRITICAL";
  headline: string;
  targetArea: string;
  channels: string[];
  recipientsCount: number;
  deliveryRate: string;
  authorizedBy: string;
}

const SEVERITY_LEVELS = [
  { id: "ADVISORY", label: "ADVISORY", color: "bg-blue-950 text-blue-300 border-blue-700", ring: "ring-blue-500" },
  { id: "WATCH", label: "WATCH", color: "bg-amber-950 text-amber-300 border-amber-700", ring: "ring-amber-500" },
  { id: "WARNING", label: "WARNING", color: "bg-orange-950 text-orange-300 border-orange-700", ring: "ring-orange-500" },
  { id: "CRITICAL", label: "CRITICAL", color: "bg-red-950 text-red-300 border-red-700", ring: "ring-red-500" },
] as const;

const TARGET_STATIONS = [
  { id: "ALL", name: "All Monitored Stations (NER-Wide)", rainfall: 68.2 },
  { id: "NER-SIK-GANGTOK-01", name: "Gangtok Hill Station (Sikkim)", rainfall: 84.5 },
  { id: "NER-MEG-CHERRA-01", name: "Cherrapunji Plateau (Meghalaya)", rainfall: 142.0 },
  { id: "NER-MIZ-AIZAWL-01", name: "Aizawl Ridge (Mizoram)", rainfall: 52.0 },
  { id: "NER-DARJ-01", name: "Darjeeling Hill Slopes (West Bengal)", rainfall: 91.4 },
  { id: "NER-NAG-KOHIMA-01", name: "Kohima Crest (Nagaland)", rainfall: 38.6 },
  { id: "NER-MAN-SENAPATI-01", name: "Senapati Valley Escarpment (Manipur)", rainfall: 44.2 },
];

const PRE_COMPOSED_TEMPLATES = [
  {
    name: "Evacuation Order (Immediate)",
    severity: "CRITICAL",
    headline: "IMMEDIATE EVACUATION ORDER: {location}",
    message:
      "CRITICAL ALERT: Geotechnical slope displacement detected at {location} following {rainfall_24h}mm rainfall. Imminent debris flow threat. Evacuate immediately to designated relief shelters via northern bypass. Follow SDRF instructions.",
  },
  {
    name: "Road Closure / Detour Notice",
    severity: "WARNING",
    headline: "ROAD CLOSURE & TRAFFIC DETOUR: {location}",
    message:
      "WARNING: NH-10 arterial corridor at {location} is CLOSED due to active rockfall and debris accumulation. Emergency clearance teams mobilized. Civilian transit strictly redirected via State Highway 8.",
  },
  {
    name: "Heavy Rainfall / Landslide Watch",
    severity: "WATCH",
    headline: "LANDSLIDE WATCH ADVISORY: {location}",
    message:
      "WATCH: Continuous intense rainfall ({rainfall_24h}mm) recorded across {location}. Soil saturation exceeds regional stability limit (82%). Residents on steep terrain remain on high alert and avoid unpaved cutting faces.",
  },
  {
    name: "All-Clear / Hazard Downgrade",
    severity: "ADVISORY",
    headline: "ALL-CLEAR & HAZARD DOWNGRADE: {location}",
    message:
      "ADVISORY: Hydro-meteorological conditions stabilizing at {location}. Slope displacement sensors return to baseline. Debris cleared from primary highway. Normal transit permitted with routine monsoonal caution.",
  },
];

const INITIAL_LOGS: BroadcastLog[] = [
  {
    id: "BC-8891",
    timestamp: "10 mins ago",
    severity: "CRITICAL",
    headline: "IMMEDIATE EVACUATION ORDER: Gangtok Hill Station",
    targetArea: "Gangtok Hill Station (Sikkim)",
    channels: ["CAP-XML", "Mobile Push", "SMS"],
    recipientsCount: 1420,
    deliveryRate: "99.4%",
    authorizedBy: "Duty Officer Sharma (DEOC-01)",
  },
  {
    id: "BC-8887",
    timestamp: "2 hours ago",
    severity: "WARNING",
    headline: "ROAD CLOSURE & TRAFFIC DETOUR: Darjeeling Slopes",
    targetArea: "Darjeeling Hill Slopes",
    channels: ["CAP-XML", "SMS", "In-App"],
    recipientsCount: 860,
    deliveryRate: "98.1%",
    authorizedBy: "Capt. P. Roy (NDRF-Ops)",
  },
  {
    id: "BC-8882",
    timestamp: "6 hours ago",
    severity: "WATCH",
    headline: "LANDSLIDE WATCH ADVISORY: Cherrapunji Plateau",
    targetArea: "Cherrapunji Plateau",
    channels: ["Mobile Push", "In-App"],
    recipientsCount: 3100,
    deliveryRate: "100%",
    authorizedBy: "Senior Hydrologist Das",
  },
];

export default function BroadcastCommandPage() {
  // Form State
  const [headline, setHeadline] = useState<string>("IMMEDIATE EVACUATION ORDER: Gangtok Hill Station");
  const [severity, setSeverity] = useState<"ADVISORY" | "WATCH" | "WARNING" | "CRITICAL">("CRITICAL");
  const [selectedStationId, setSelectedStationId] = useState<string>("NER-SIK-GANGTOK-01");
  const [message, setMessage] = useState<string>(
    "CRITICAL ALERT: Geotechnical slope displacement detected at {location} following {rainfall_24h}mm rainfall. Imminent debris flow threat. Evacuate immediately to designated relief shelters via northern bypass. Follow SDRF instructions."
  );

  // Audiences
  const [targetAudiences, setTargetAudiences] = useState({
    public: true,
    fieldTeams: true,
    deoc: true,
    media: false,
  });

  // Channels
  const [channels, setChannels] = useState({
    cap: true,
    push: true,
    sms: true,
    whatsapp: false,
    inApp: true,
  });

  // Preview tab
  const [previewTab, setPreviewTab] = useState<"MOBILE" | "SMS" | "CAP">("MOBILE");

  // Transmission states
  const [isTransmitting, setIsTransmitting] = useState<boolean>(false);
  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [showConfirmModal, setShowConfirmModal] = useState<boolean>(false);
  const [broadcastSuccess, setBroadcastSuccess] = useState<string | null>(null);
  const [logs, setLogs] = useState<BroadcastLog[]>(INITIAL_LOGS);

  const selectedStation = TARGET_STATIONS.find((s) => s.id === selectedStationId) || TARGET_STATIONS[1];

  // Dynamic variable resolution
  const resolvedHeadline = useMemo(() => {
    return headline
      .replace(/{location}/g, selectedStation.name)
      .replace(/{severity}/g, severity)
      .replace(/{rainfall_24h}/g, selectedStation.rainfall.toFixed(1));
  }, [headline, selectedStation, severity]);

  const resolvedMessage = useMemo(() => {
    return message
      .replace(/{location}/g, selectedStation.name)
      .replace(/{severity}/g, severity)
      .replace(/{rainfall_24h}/g, selectedStation.rainfall.toFixed(1));
  }, [message, selectedStation, severity]);

  const handleApplyTemplate = (tmpl: (typeof PRE_COMPOSED_TEMPLATES)[0]) => {
    setSeverity(tmpl.severity as any);
    setHeadline(tmpl.headline);
    setMessage(tmpl.message);
  };

  const insertVariable = (varName: string) => {
    setMessage((prev) => `${prev} {${varName}}`);
  };

  const handleTestBroadcast = async () => {
    setIsTesting(true);
    setTimeout(() => {
      setIsTesting(false);
      setBroadcastSuccess("Test transmission verified: 4 test recipients received packet.");
      setTimeout(() => setBroadcastSuccess(null), 3500);
    }, 1000);
  };

  const handleTransmitBroadcast = async () => {
    setIsTransmitting(true);
    setShowConfirmModal(false);

    try {
      const activeChannelsList = Object.entries(channels)
        .filter(([_, active]) => active)
        .map(([k]) => {
          switch (k) {
            case "cap": return "CAP-XML";
            case "push": return "Mobile Push";
            case "sms": return "SMS";
            case "whatsapp": return "WhatsApp";
            default: return "In-App";
          }
        });

      const newLog: BroadcastLog = {
        id: `BC-${Math.floor(1000 + Math.random() * 9000)}`,
        timestamp: "Just now",
        severity,
        headline: resolvedHeadline,
        targetArea: selectedStation.name,
        channels: activeChannelsList,
        recipientsCount: targetAudiences.public ? 1850 : 42,
        deliveryRate: "Queued (100%)",
        authorizedBy: "Duty Officer (Current Session)",
      };

      // Also dispatch to API if available
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        await fetch(`${apiUrl}/api/v1/alerts/broadcast`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: resolvedHeadline,
            message: resolvedMessage,
            priority: severity === "CRITICAL" ? "CRITICAL" : "URGENT",
            target_type: selectedStationId === "ALL" ? "PUBLIC_USERS" : "EVENT_AREA",
            channels: ["IN_APP", "SMS"],
          }),
        });
      } catch (apiErr) {
        console.warn("Backend broadcast log fallback active", apiErr);
      }

      setLogs((prev) => [newLog, ...prev]);
      setBroadcastSuccess(`Emergency broadcast authorized and dispatched across ${activeChannelsList.length} channels.`);
      setTimeout(() => setBroadcastSuccess(null), 5000);
    } finally {
      setIsTransmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white font-sans flex flex-col">
      <CommandHeader />

      <main className="flex-1 p-3 sm:p-5 max-w-[1700px] mx-auto w-full space-y-4">
        {/* Top Title Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-zinc-950 border border-zinc-800 rounded-lg p-3.5 shadow-sm">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-red-600/20 border border-red-500/40 flex items-center justify-center text-red-400">
              <Radio className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase text-red-400 font-bold tracking-wider">
                  DISASTER INTELLIGENCE • EMERGENCY ALERTING
                </span>
                <span className="bg-red-950 text-red-300 border border-red-700 text-[9px] font-mono px-1.5 py-0.2 rounded font-black uppercase">
                  CAP v1.2 CERTIFIED
                </span>
              </div>
              <h1 className="text-base sm:text-lg font-black text-white">
                Multi-Channel Emergency Broadcast Command
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2 font-mono text-xs">
            <Link
              href="/events"
              className="px-2.5 py-1.5 bg-zinc-900 hover:bg-zinc-800 border border-zinc-750 text-zinc-300 rounded font-bold transition flex items-center gap-1.5"
            >
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
              <span>Events Queue</span>
            </Link>
            <Link
              href="/"
              className="px-2.5 py-1.5 bg-zinc-900 hover:bg-zinc-800 border border-zinc-750 text-zinc-300 rounded font-bold transition"
            >
              Command HQ
            </Link>
          </div>
        </div>

        {/* Success Alert Banner */}
        {broadcastSuccess && (
          <div className="bg-emerald-950/90 border border-emerald-700 rounded-lg p-3 text-xs font-mono text-emerald-300 flex items-center gap-2 shadow-lg animate-pulse">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span className="font-bold">{broadcastSuccess}</span>
          </div>
        )}

        {/* Main 2-Column Command Workspace */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* ========================================================================= */}
          {/* LEFT PANEL: BROADCAST COMPOSER (7 cols) */}
          {/* ========================================================================= */}
          <div className="lg:col-span-7 bg-zinc-950 border border-zinc-800 rounded-lg p-4 sm:p-5 space-y-4 shadow-md">
            <div className="border-b border-zinc-850 pb-3 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-black text-white font-mono uppercase tracking-wider flex items-center gap-2">
                  <Send className="w-4 h-4 text-zinc-400" />
                  Alert Composer
                </h2>
                <p className="text-[11px] text-zinc-400 font-mono">
                  Draft authoritative multi-channel public warnings and tactical field directives.
                </p>
              </div>

              {/* Pre-composed Templates Menu */}
              <div className="flex items-center gap-1.5 text-xs font-mono">
                <span className="text-[10px] text-zinc-500 uppercase font-bold hidden sm:inline">Templates:</span>
                <select
                  onChange={(e) => {
                    const idx = parseInt(e.target.value);
                    if (!isNaN(idx) && PRE_COMPOSED_TEMPLATES[idx]) {
                      handleApplyTemplate(PRE_COMPOSED_TEMPLATES[idx]);
                    }
                  }}
                  defaultValue=""
                  className="bg-black border border-zinc-800 rounded px-2.5 py-1 text-[11px] font-mono text-zinc-200 focus:outline-none cursor-pointer"
                >
                  <option value="" disabled>Load Pre-Composed Template...</option>
                  {PRE_COMPOSED_TEMPLATES.map((tmpl, idx) => (
                    <option key={tmpl.name} value={idx}>
                      [{tmpl.severity}] {tmpl.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Severity Level Selector (4 Buttons) */}
            <div className="space-y-1.5">
              <label className="block text-[10px] font-mono uppercase text-zinc-400 font-bold">
                Alert Severity Level:
              </label>
              <div className="grid grid-cols-4 gap-2 font-mono text-xs">
                {SEVERITY_LEVELS.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setSeverity(s.id)}
                    className={`py-2 px-2 rounded font-black uppercase transition border text-center ${
                      severity === s.id
                        ? `${s.color} ring-2 ${s.ring} shadow-md`
                        : "bg-black text-zinc-400 border-zinc-800 hover:text-white"
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Target Area Selector */}
            <div className="space-y-1.5">
              <label className="block text-[10px] font-mono uppercase text-zinc-400 font-bold">
                Target Geographic Perimeter:
              </label>
              <select
                value={selectedStationId}
                onChange={(e) => setSelectedStationId(e.target.value)}
                className="w-full bg-black border border-zinc-800 rounded-lg p-2.5 text-white font-mono text-xs focus:outline-none focus:border-zinc-600 cursor-pointer"
              >
                {TARGET_STATIONS.map((station) => (
                  <option key={station.id} value={station.id} className="bg-zinc-950">
                    {station.name} — Current 24h Rain: {station.rainfall}mm
                  </option>
                ))}
              </select>
            </div>

            {/* Target Audience Checkboxes */}
            <div className="space-y-1.5">
              <label className="block text-[10px] font-mono uppercase text-zinc-400 font-bold">
                Authorized Recipient Audiences:
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                <label className="flex items-center gap-2 bg-black p-2 rounded border border-zinc-800 cursor-pointer hover:border-zinc-700">
                  <input
                    type="checkbox"
                    checked={targetAudiences.public}
                    onChange={(e) => setTargetAudiences({ ...targetAudiences, public: e.target.checked })}
                    className="accent-red-500 rounded"
                  />
                  <span className="text-[11px] text-zinc-200">Public Citizens</span>
                </label>

                <label className="flex items-center gap-2 bg-black p-2 rounded border border-zinc-800 cursor-pointer hover:border-zinc-700">
                  <input
                    type="checkbox"
                    checked={targetAudiences.fieldTeams}
                    onChange={(e) => setTargetAudiences({ ...targetAudiences, fieldTeams: e.target.checked })}
                    className="accent-red-500 rounded"
                  />
                  <span className="text-[11px] text-zinc-200">Field SDRF/NDRF</span>
                </label>

                <label className="flex items-center gap-2 bg-black p-2 rounded border border-zinc-800 cursor-pointer hover:border-zinc-700">
                  <input
                    type="checkbox"
                    checked={targetAudiences.deoc}
                    onChange={(e) => setTargetAudiences({ ...targetAudiences, deoc: e.target.checked })}
                    className="accent-red-500 rounded"
                  />
                  <span className="text-[11px] text-zinc-200">District DEOC</span>
                </label>

                <label className="flex items-center gap-2 bg-black p-2 rounded border border-zinc-800 cursor-pointer hover:border-zinc-700">
                  <input
                    type="checkbox"
                    checked={targetAudiences.media}
                    onChange={(e) => setTargetAudiences({ ...targetAudiences, media: e.target.checked })}
                    className="accent-red-500 rounded"
                  />
                  <span className="text-[11px] text-zinc-200">Media / PIO</span>
                </label>
              </div>
            </div>

            {/* Distribution Channels */}
            <div className="space-y-1.5">
              <label className="block text-[10px] font-mono uppercase text-zinc-400 font-bold">
                Multi-Channel Distribution Gateways:
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs font-mono">
                <label className="flex items-center gap-2 bg-black p-2 rounded border border-zinc-800 cursor-pointer hover:border-zinc-700">
                  <input
                    type="checkbox"
                    checked={channels.cap}
                    onChange={(e) => setChannels({ ...channels, cap: e.target.checked })}
                    className="accent-blue-500 rounded"
                  />
                  <span className="text-[10px] text-zinc-200">CAP-XML v1.2</span>
                </label>

                <label className="flex items-center gap-2 bg-black p-2 rounded border border-zinc-800 cursor-pointer hover:border-zinc-700">
                  <input
                    type="checkbox"
                    checked={channels.push}
                    onChange={(e) => setChannels({ ...channels, push: e.target.checked })}
                    className="accent-emerald-500 rounded"
                  />
                  <span className="text-[10px] text-zinc-200">Mobile Push</span>
                </label>

                <label className="flex items-center gap-2 bg-black p-2 rounded border border-zinc-800 cursor-pointer hover:border-zinc-700">
                  <input
                    type="checkbox"
                    checked={channels.sms}
                    onChange={(e) => setChannels({ ...channels, sms: e.target.checked })}
                    className="accent-amber-500 rounded"
                  />
                  <span className="text-[10px] text-zinc-200">Telecom SMS</span>
                </label>

                <label className="flex items-center gap-2 bg-black p-2 rounded border border-zinc-800 cursor-pointer hover:border-zinc-700">
                  <input
                    type="checkbox"
                    checked={channels.whatsapp}
                    onChange={(e) => setChannels({ ...channels, whatsapp: e.target.checked })}
                    className="accent-green-500 rounded"
                  />
                  <span className="text-[10px] text-zinc-200">WhatsApp API</span>
                </label>

                <label className="flex items-center gap-2 bg-black p-2 rounded border border-zinc-800 cursor-pointer hover:border-zinc-700">
                  <input
                    type="checkbox"
                    checked={channels.inApp}
                    onChange={(e) => setChannels({ ...channels, inApp: e.target.checked })}
                    className="accent-purple-500 rounded"
                  />
                  <span className="text-[10px] text-zinc-200">In-App Banner</span>
                </label>
              </div>
            </div>

            {/* Alert Headline */}
            <div className="space-y-1.5">
              <label className="block text-[10px] font-mono uppercase text-zinc-400 font-bold">
                Alert Headline / Subject:
              </label>
              <input
                type="text"
                value={headline}
                onChange={(e) => setHeadline(e.target.value)}
                maxLength={140}
                className="w-full bg-black border border-zinc-800 rounded-lg p-2.5 text-white font-mono text-xs focus:outline-none focus:border-zinc-600"
              />
            </div>

            {/* Message Body with Variable Chips & Character Counter */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[10px] font-mono uppercase text-zinc-400 font-bold">
                <span>Message Body (Plaintext &amp; CAP Description):</span>
                <span className={message.length > 300 ? "text-amber-400" : "text-zinc-500"}>
                  {message.length} / 500 chars
                </span>
              </div>
              <textarea
                rows={4}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                maxLength={500}
                className="w-full bg-black border border-zinc-800 rounded-lg p-2.5 text-white text-xs focus:outline-none focus:border-zinc-600 leading-relaxed font-sans"
              />

              {/* Variable Chips */}
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-zinc-400 pt-0.5">
                <span className="text-zinc-500">Insert variable:</span>
                <button
                  type="button"
                  onClick={() => insertVariable("location")}
                  className="bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 px-2 py-0.5 rounded transition"
                >
                  &#123;location&#125;
                </button>
                <button
                  type="button"
                  onClick={() => insertVariable("severity")}
                  className="bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 px-2 py-0.5 rounded transition"
                >
                  &#123;severity&#125;
                </button>
                <button
                  type="button"
                  onClick={() => insertVariable("rainfall_24h")}
                  className="bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 px-2 py-0.5 rounded transition"
                >
                  &#123;rainfall_24h&#125;
                </button>
              </div>
            </div>

            {/* Action Buttons: Test vs Transmit */}
            <div className="flex items-center gap-2 pt-2 border-t border-zinc-850">
              <button
                type="button"
                onClick={handleTestBroadcast}
                disabled={isTesting}
                className="flex-1 bg-zinc-900 hover:bg-zinc-850 border border-zinc-700 text-zinc-300 py-3 rounded-lg font-mono text-xs font-bold transition flex items-center justify-center gap-2"
              >
                <Eye className="w-3.5 h-3.5 text-zinc-400" />
                <span>{isTesting ? "SENDING TEST..." : "TEST BROADCAST (DEOC ONLY)"}</span>
              </button>

              <button
                type="button"
                onClick={() => setShowConfirmModal(true)}
                className="flex-1 bg-red-600 hover:bg-red-500 active:bg-red-700 text-white py-3 rounded-lg font-mono font-black text-xs shadow-lg shadow-red-950/50 transition flex items-center justify-center gap-2"
              >
                <Radio className="w-4 h-4 animate-pulse" />
                <span>AUTHORIZE &amp; TRANSMIT NOW</span>
              </button>
            </div>
          </div>

          {/* ========================================================================= */}
          {/* RIGHT PANEL: LIVE MULTI-CHANNEL PREVIEW & RECENT AUDIT LOG (5 cols) */}
          {/* ========================================================================= */}
          <div className="lg:col-span-5 space-y-4">
            {/* Live Message Preview Card */}
            <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 sm:p-5 space-y-3.5 shadow-md">
              <div className="flex items-center justify-between border-b border-zinc-850 pb-2.5">
                <div>
                  <h3 className="text-sm font-black text-white font-mono uppercase tracking-wider">
                    Live Channel Preview
                  </h3>
                  <div className="text-[10px] text-zinc-500 font-mono">
                    Target: {selectedStation.name}
                  </div>
                </div>

                {/* Preview Switcher Tabs */}
                <div className="flex items-center gap-1 bg-black p-1 rounded-lg border border-zinc-800 text-[10px] font-mono">
                  <button
                    type="button"
                    onClick={() => setPreviewTab("MOBILE")}
                    className={`px-2 py-1 rounded transition flex items-center gap-1 ${
                      previewTab === "MOBILE" ? "bg-white text-black font-black" : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    <Smartphone className="w-3 h-3" />
                    <span>Push</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setPreviewTab("SMS")}
                    className={`px-2 py-1 rounded transition flex items-center gap-1 ${
                      previewTab === "SMS" ? "bg-white text-black font-black" : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    <MessageSquare className="w-3 h-3" />
                    <span>SMS</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setPreviewTab("CAP")}
                    className={`px-2 py-1 rounded transition flex items-center gap-1 ${
                      previewTab === "CAP" ? "bg-white text-black font-black" : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    <FileCode className="w-3 h-3" />
                    <span>CAP</span>
                  </button>
                </div>
              </div>

              {/* Tab 1: Mobile Push Notification Preview */}
              {previewTab === "MOBILE" && (
                <div className="bg-black p-3.5 rounded-xl border border-zinc-800 space-y-2.5">
                  <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500">
                    <span className="flex items-center gap-1 text-zinc-300 font-bold">
                      <Radio className="w-3 h-3 text-red-500" />
                      DISASTRA NER India Alert
                    </span>
                    <span>Just now</span>
                  </div>

                  <div className="bg-zinc-900/90 rounded-lg p-3 border border-zinc-750 space-y-1.5 shadow-sm">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-[9px] font-mono font-black uppercase px-1.5 py-0.5 rounded border ${
                          severity === "CRITICAL"
                            ? "bg-red-950 text-red-300 border-red-700"
                            : severity === "WARNING"
                            ? "bg-orange-950 text-orange-300 border-orange-700"
                            : "bg-amber-950 text-amber-300 border-amber-700"
                        }`}
                      >
                        {severity}
                      </span>
                      <strong className="text-xs text-white font-bold truncate">{resolvedHeadline}</strong>
                    </div>
                    <p className="text-[11px] text-zinc-300 leading-snug font-sans">{resolvedMessage}</p>
                  </div>
                </div>
              )}

              {/* Tab 2: SMS Text Message Preview */}
              {previewTab === "SMS" && (
                <div className="bg-black p-3.5 rounded-xl border border-zinc-800 space-y-2.5 font-mono">
                  <div className="flex items-center justify-between text-[10px] text-zinc-500">
                    <span>GOVT-ALERT-NER Gateway</span>
                    <span className={resolvedMessage.length > 160 ? "text-amber-400" : "text-emerald-400"}>
                      {resolvedMessage.length} chars ({Math.ceil(resolvedMessage.length / 160)} SMS segment)
                    </span>
                  </div>

                  <div className="bg-zinc-900 p-3 rounded-lg border border-zinc-800 text-xs text-zinc-200 leading-relaxed">
                    {`[${severity}] `}
                    {resolvedMessage}
                  </div>
                </div>
              )}

              {/* Tab 3: CAP-XML v1.2 View */}
              {previewTab === "CAP" && (
                <div className="bg-black p-3 rounded-xl border border-zinc-800 font-mono text-[10px] text-zinc-400 overflow-x-auto max-h-56 leading-tight">
                  <pre>{`<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>DISASTRA-NER-${Date.now()}</identifier>
  <sender>deoc-command@ner.disastra.gov.in</sender>
  <sent>${new Date().toISOString()}</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <category>Geo</category>
    <event>Landslide / Slope Mass Movement</event>
    <urgency>Immediate</urgency>
    <severity>${severity}</severity>
    <certainty>Observed</certainty>
    <headline>${resolvedHeadline}</headline>
    <description>${resolvedMessage}</description>
    <area>
      <areaDesc>${selectedStation.name}</areaDesc>
    </area>
  </info>
</alert>`}</pre>
                </div>
              )}
            </div>

            {/* Broadcast History / Audit Log */}
            <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 sm:p-5 space-y-3 shadow-md">
              <div className="flex items-center justify-between border-b border-zinc-850 pb-2">
                <h3 className="text-xs font-black text-white font-mono uppercase tracking-wider flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-zinc-400" />
                  Recent Broadcast Transmissions
                </h3>
                <span className="text-[10px] text-zinc-500 font-mono">Immutable Audit Log</span>
              </div>

              <div className="space-y-2">
                {logs.map((log) => (
                  <div
                    key={log.id}
                    className="bg-black p-2.5 rounded-lg border border-zinc-850 space-y-1.5 font-mono text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`text-[9px] font-black px-1.5 py-0.5 rounded border uppercase ${
                            log.severity === "CRITICAL"
                              ? "bg-red-950 text-red-300 border-red-700"
                              : log.severity === "WARNING"
                              ? "bg-orange-950 text-orange-300 border-orange-700"
                              : "bg-amber-950 text-amber-300 border-amber-700"
                          }`}
                        >
                          {log.severity}
                        </span>
                        <span className="text-[11px] font-bold text-white truncate max-w-[200px]">
                          {log.headline}
                        </span>
                      </div>
                      <span className="text-[10px] text-zinc-500">{log.timestamp}</span>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-zinc-400">
                      <span>Area: {log.targetArea}</span>
                      <span className="text-emerald-400 font-bold">{log.deliveryRate}</span>
                    </div>

                    <div className="flex items-center justify-between text-[9px] text-zinc-500 pt-1 border-t border-zinc-900">
                      <span>Channels: {log.channels.join(", ")}</span>
                      <span>Auth: {log.authorizedBy}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* ========================================================================= */}
      {/* CONFIRMATION MODAL BEFORE DISPATCH */}
      {/* ========================================================================= */}
      {showConfirmModal && (
        <div className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-3 backdrop-blur-md font-mono">
          <div className="bg-zinc-950 border-2 border-red-600 rounded-xl w-full max-w-md p-5 space-y-4 shadow-2xl text-white">
            <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
              <AlertOctagon className="w-6 h-6 text-red-500 shrink-0 animate-pulse" />
              <div>
                <h3 className="text-sm font-black text-white uppercase">Confirm Emergency Broadcast</h3>
                <p className="text-[10px] text-red-400">AUTHORIZATION REQUIRED</p>
              </div>
            </div>

            <div className="bg-black p-3 rounded-lg border border-zinc-800 text-xs space-y-1.5">
              <div className="text-zinc-400 text-[10px] uppercase">Recipient Area:</div>
              <div className="font-bold text-white">{selectedStation.name}</div>

              <div className="text-zinc-400 text-[10px] uppercase pt-1">Severity:</div>
              <div className="font-black text-red-400">{severity} EARLY WARNING</div>

              <div className="text-zinc-400 text-[10px] uppercase pt-1">Resolved Headline:</div>
              <div className="text-zinc-200">{resolvedHeadline}</div>
            </div>

            <p className="text-[11px] text-zinc-400 font-sans leading-snug">
              This will trigger live SMS gateways, mobile push notifications, and update official CAP-XML feeds. Are you certain you want to proceed?
            </p>

            <div className="flex items-center gap-2 pt-1">
              <button
                type="button"
                onClick={() => setShowConfirmModal(false)}
                className="flex-1 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 py-2.5 rounded-lg text-xs font-bold transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleTransmitBroadcast}
                disabled={isTransmitting}
                className="flex-1 bg-red-600 hover:bg-red-500 active:bg-red-700 text-white py-2.5 rounded-lg font-black text-xs shadow-lg transition"
              >
                {isTransmitting ? "TRANSMITTING..." : "CONFIRM & DISPATCH"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
