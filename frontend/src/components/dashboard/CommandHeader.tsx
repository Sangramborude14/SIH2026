"use client";

import React from "react";
import {
  Activity,
  Radio,
  Sliders,
  Wifi,
  CloudDownload,
  RefreshCw,
  Clock,
  Send,
  Layers,
  MapPin,
  AlertTriangle,
  Server,
  Shield,
  Smartphone,
  Globe,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface CommandHeaderProps {
  engineOnline?: boolean;
  engineStatusText?: string;
  lastUpdated?: string | null;
  dataSourcesStatus?: string;
  dataMode?: string;
  onToggleDataMode?: (mode: string) => Promise<void> | void;
  onTriggerEngineRun?: () => void;
  onTriggerBatchIngest?: () => void;
  isRunningEngine?: boolean;
  isIngesting?: boolean;
  autoRefreshInterval?: number;
  onToggleAutoRefresh?: (interval: number) => void;
  bhoonidhiStatus?: string;
  fieldActiveCount?: number;
  mlModelStatus?: string;
  mlModelVersion?: string;
  mlIsTrained?: boolean;
}

export default function CommandHeader({
  engineOnline = true,
  engineStatusText = "ONLINE",
  lastUpdated = null,
  dataSourcesStatus = "HEALTHY",
  dataMode = "LIVE",
  onToggleDataMode = async () => {},
  onTriggerEngineRun,
  onTriggerBatchIngest,
  isRunningEngine = false,
  isIngesting = false,
  autoRefreshInterval = 30,
  onToggleAutoRefresh,
  bhoonidhiStatus = "NOT_CONFIGURED",
  fieldActiveCount = 3,
  mlModelStatus = "READY",
  mlModelVersion = "2.1.0",
  mlIsTrained = true,
}: CommandHeaderProps = {}) {
  const pathname = usePathname();
  const isLiveMode = (dataMode || "LIVE").toUpperCase() === "LIVE";
  const displayEngineStatus = isRunningEngine ? "RUNNING" : engineOnline ? engineStatusText : "OFFLINE";
  const isDataHealthy = engineOnline && (dataSourcesStatus.includes("HEALTHY") || dataSourcesStatus.includes("OPERATIONAL"));

  const navItems = [
    { href: "/", label: "Overview", icon: Layers },
    { href: "/stations", label: "Stations 360", icon: MapPin },
    { href: "/events", label: "Events Queue", icon: AlertTriangle },
    { href: "/field", label: "Field Operations", icon: Radio },
    { href: "/analytics", label: "Model Analytics", icon: Activity },
    { href: "/broadcast", label: "Broadcast", icon: Send },
    { href: "/system", label: "System Health", icon: Server },
  ];

  return (
    <header className="bg-black border-b border-zinc-800 font-sans text-white sticky top-0 z-40">
      {/* Top Header Strip */}
      <div className="px-4 py-2.5 sm:px-6 flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-zinc-800">
        {/* Left: Branding & Core Mode */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-white text-black flex items-center justify-center font-black font-mono text-xs shadow-sm">
            NDMA
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono tracking-widest text-emerald-400 uppercase font-bold">
                DISASTRA &bull; NORTH EASTERN REGION EARLY WARNING
              </span>
              <span className="bg-zinc-900 text-zinc-300 border border-zinc-700 text-[9px] font-mono px-1.5 py-0.2 rounded font-bold">
                v2.1.0 AI/ML
              </span>
            </div>
            <h1 className="text-base sm:text-lg font-black tracking-tight text-white flex items-center gap-2">
              Disaster Intelligence Command Center
            </h1>
          </div>
        </div>

        {/* Right: Operational Controls */}
        <div className="flex items-center gap-2 flex-wrap text-xs font-mono">
          {/* Mode Switcher */}
          <div className="flex items-center bg-zinc-900 p-0.5 rounded border border-zinc-800 text-xs">
            <button
              onClick={() => onToggleDataMode("LIVE")}
              className={`px-2.5 py-1 rounded transition font-bold flex items-center gap-1.5 ${
                isLiveMode ? "bg-white text-black shadow-sm" : "text-zinc-400 hover:text-white"
              }`}
            >
              <Wifi className="w-3 h-3 text-emerald-600" />
              LIVE
            </button>
            <button
              onClick={() => onToggleDataMode("SIMULATION")}
              className={`px-2.5 py-1 rounded transition font-bold flex items-center gap-1.5 ${
                !isLiveMode ? "bg-white text-black shadow-sm" : "text-zinc-400 hover:text-white"
              }`}
            >
              <Sliders className="w-3 h-3 text-amber-500" />
              SIMULATION
            </button>
          </div>

          {/* Ingest Button */}
          {isLiveMode && onTriggerBatchIngest && (
            <button
              onClick={onTriggerBatchIngest}
              disabled={isIngesting}
              className="bg-zinc-900 hover:bg-zinc-800 text-white border border-zinc-700 text-xs font-bold px-2.5 py-1 rounded transition flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
            >
              <CloudDownload className={`w-3.5 h-3.5 ${isIngesting ? "animate-spin" : ""}`} />
              {isIngesting ? "Ingesting..." : "Ingest Telemetry"}
            </button>
          )}

          {/* Manual Run Engine */}
          {onTriggerEngineRun && (
            <button
              onClick={onTriggerEngineRun}
              disabled={isRunningEngine}
              className="bg-white hover:bg-zinc-200 text-black text-xs font-black px-3 py-1 rounded transition flex items-center gap-1.5 shadow-sm disabled:opacity-50 cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRunningEngine ? "animate-spin" : ""}`} />
              {isRunningEngine ? "Assessing..." : "Run Engine"}
            </button>
          )}

          {/* Auto Refresh Select */}
          {onToggleAutoRefresh && (
            <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 px-2 py-1 rounded text-xs">
              <Clock className="w-3 h-3 text-zinc-400" />
              <select
                value={autoRefreshInterval}
                onChange={(e) => onToggleAutoRefresh(Number(e.target.value))}
                className="bg-transparent text-zinc-200 focus:outline-none text-xs cursor-pointer font-mono font-bold"
              >
                <option value={15} className="bg-zinc-950 text-white">15s</option>
                <option value={30} className="bg-zinc-950 text-white">30s</option>
                <option value={60} className="bg-zinc-950 text-white">60s</option>
                <option value={0} className="bg-zinc-950 text-white">Manual</option>
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Understated Mission Control Status Strip */}
      <div className="bg-zinc-950 px-4 py-1.5 sm:px-6 flex flex-wrap items-center justify-between gap-3 text-[10px] font-mono border-b border-zinc-850 text-zinc-400">
        <div className="flex items-center gap-3.5 flex-wrap">
          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 uppercase font-semibold">ENGINE:</span>
            <span
              className={`font-black ${
                displayEngineStatus === "ONLINE" || displayEngineStatus === "RUNNING"
                  ? "text-emerald-400"
                  : displayEngineStatus === "STARTING" || displayEngineStatus === "DEGRADED"
                  ? "text-amber-400"
                  : "text-red-400"
              }`}
            >
              {displayEngineStatus}
            </span>
          </div>

          <span className="text-zinc-700">|</span>

          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 uppercase font-semibold">TELEMETRY:</span>
            <span className={`font-bold ${isDataHealthy ? "text-emerald-400" : "text-amber-400"}`}>
              {engineOnline ? (isDataHealthy ? "HEALTHY" : "DEGRADED") : "OFFLINE"}
            </span>
          </div>

          <span className="text-zinc-700">|</span>

          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 uppercase font-semibold">24H FORECAST:</span>
            <span className="text-white font-bold">ACTIVE</span>
          </div>

          <span className="text-zinc-700">|</span>

          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 uppercase font-semibold">ML MODEL:</span>
            <span className={`font-black ${mlIsTrained ? "text-emerald-400" : "text-amber-400"}`}>
              {mlIsTrained ? `READY (${mlModelVersion})` : "FALLBACK"}
            </span>
          </div>

          <span className="text-zinc-700">|</span>

          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 uppercase font-semibold">FIELD OPS:</span>
            <span className="text-white font-bold">{fieldActiveCount} UNITS ACTIVE</span>
          </div>
        </div>

        <div className="text-zinc-500 text-[10px]">
          Sync: {lastUpdated || "00:00:00 UTC"}
        </div>
      </div>

      {/* Main Navigation Bar (Same-Tab SPA Navigation) */}
      <div className="px-4 sm:px-6 bg-black flex items-center justify-between text-xs font-mono overflow-x-auto">
        <nav className="flex items-center gap-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`px-3.5 py-2 border-b-2 font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                  isActive
                    ? "border-white text-white bg-zinc-900"
                    : "border-transparent text-zinc-400 hover:text-white hover:bg-zinc-900/50"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Understated External / Public Portals Links */}
        <div className="hidden lg:flex items-center gap-2 text-[11px] font-mono text-zinc-500 pl-4 border-l border-zinc-800 my-1">
          <Link
            href="/citizen"
            className="hover:text-zinc-300 flex items-center gap-1 py-1 px-2 rounded hover:bg-zinc-900 transition"
          >
            <Smartphone className="w-3 h-3 text-emerald-400" />
            <span>Citizen App</span>
          </Link>
          <Link
            href="/public"
            className="hover:text-zinc-300 flex items-center gap-1 py-1 px-2 rounded hover:bg-zinc-900 transition"
          >
            <Globe className="w-3 h-3 text-blue-400" />
            <span>Public Portal</span>
          </Link>
        </div>
      </div>
    </header>
  );
}
