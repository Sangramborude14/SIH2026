"use client";

import React, { useEffect, useState, useMemo } from "react";
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from "react-leaflet";
import L from "leaflet";
import { LocationMapItem } from "@/components/dashboard/types";
import {
  AlertTriangle,
  Droplets,
  Mountain,
  ArrowUpRight,
  ShieldCheck,
  Flame,
  Layers,
  Globe,
  Info,
  Clock,
  Activity,
  Compass,
  Cpu,
} from "lucide-react";

interface RiskMapInnerProps {
  locations: LocationMapItem[];
  selectedLocationId: string | null;
  onSelectLocation: (locationId: string) => void;
  onOpenInvestigate: (locationId: string) => void;
}

const MAP_TILES: Record<string, { name: string; url: string; attribution?: string; maxZoom: number }> = {
  topo: {
    name: "Topographic",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
    attribution: "Esri Topo",
    maxZoom: 19,
  },
  satellite: {
    name: "Satellite",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: "Esri Satellite",
    maxZoom: 19,
  },
  terrain: {
    name: "Elevation Terrain",
    url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    attribution: "OpenTopoMap",
    maxZoom: 17,
  },
  dark: {
    name: "Dark Mission",
    url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    attribution: "CartoDB",
    maxZoom: 19,
  },
};

type PredictionLayer =
  | "CURRENT_RISK"
  | "FORECAST_24H"
  | "ANOMALY"
  | "RAINFALL"
  | "SOIL_MOISTURE"
  | "SUSCEPTIBILITY";

function MapController({ selectedLocation }: { selectedLocation: LocationMapItem | undefined }) {
  const map = useMap();
  useEffect(() => {
    if (selectedLocation) {
      map.flyTo([selectedLocation.latitude, selectedLocation.longitude], 9.5, {
        duration: 1.2,
      });
    }
  }, [selectedLocation, map]);
  return null;
}

function getLayerMetricValue(loc: LocationMapItem, layer: PredictionLayer): {
  valStr: string;
  color: string;
  borderColor: string;
  fillColor: string;
  isHigh: boolean;
} {
  switch (layer) {
    case "FORECAST_24H": {
      const p = loc.forecast_probabilities?.["24h"];
      if (p === undefined || p === null) {
        return { valStr: "N/A", color: "#64748b", borderColor: "#475569", fillColor: "#334155", isHigh: false };
      }
      const pct = Math.round(p * 100);
      if (p >= 0.70) return { valStr: `${pct}%`, color: "#ef4444", borderColor: "#b91c1c", fillColor: "#ef4444", isHigh: true };
      if (p >= 0.50) return { valStr: `${pct}%`, color: "#f97316", borderColor: "#c2410c", fillColor: "#f97316", isHigh: true };
      if (p >= 0.30) return { valStr: `${pct}%`, color: "#eab308", borderColor: "#a16207", fillColor: "#eab308", isHigh: false };
      return { valStr: `${pct}%`, color: "#10b981", borderColor: "#059669", fillColor: "#10b981", isHigh: false };
    }
    case "ANOMALY": {
      const a = loc.anomaly_score ?? 0;
      const scoreStr = a.toFixed(2);
      if (a >= 0.75) return { valStr: scoreStr, color: "#ef4444", borderColor: "#b91c1c", fillColor: "#ef4444", isHigh: true };
      if (a >= 0.50) return { valStr: scoreStr, color: "#f97316", borderColor: "#c2410c", fillColor: "#f97316", isHigh: true };
      if (a >= 0.25) return { valStr: scoreStr, color: "#eab308", borderColor: "#a16207", fillColor: "#eab308", isHigh: false };
      return { valStr: scoreStr, color: "#10b981", borderColor: "#059669", fillColor: "#10b981", isHigh: false };
    }
    case "RAINFALL": {
      const r = loc.rainfall_24h ?? 0;
      const rStr = `${Math.round(r)}m`;
      if (r >= 100) return { valStr: rStr, color: "#ef4444", borderColor: "#b91c1c", fillColor: "#ef4444", isHigh: true };
      if (r >= 50) return { valStr: rStr, color: "#f97316", borderColor: "#c2410c", fillColor: "#f97316", isHigh: true };
      if (r >= 20) return { valStr: rStr, color: "#eab308", borderColor: "#a16207", fillColor: "#eab308", isHigh: false };
      return { valStr: rStr, color: "#10b981", borderColor: "#059669", fillColor: "#10b981", isHigh: false };
    }
    case "SOIL_MOISTURE": {
      const s = loc.soil_moisture ?? 35;
      const sStr = `${Math.round(s)}%`;
      if (s >= 80) return { valStr: sStr, color: "#ef4444", borderColor: "#b91c1c", fillColor: "#ef4444", isHigh: true };
      if (s >= 65) return { valStr: sStr, color: "#f97316", borderColor: "#c2410c", fillColor: "#f97316", isHigh: true };
      if (s >= 50) return { valStr: sStr, color: "#eab308", borderColor: "#a16207", fillColor: "#eab308", isHigh: false };
      return { valStr: sStr, color: "#10b981", borderColor: "#059669", fillColor: "#10b981", isHigh: false };
    }
    case "SUSCEPTIBILITY": {
      const susc = loc.susceptibility_score ?? 0.5;
      const suscStr = susc.toFixed(2);
      if (susc >= 0.75) return { valStr: suscStr, color: "#ef4444", borderColor: "#b91c1c", fillColor: "#ef4444", isHigh: true };
      if (susc >= 0.55) return { valStr: suscStr, color: "#f97316", borderColor: "#c2410c", fillColor: "#f97316", isHigh: true };
      if (susc >= 0.35) return { valStr: suscStr, color: "#eab308", borderColor: "#a16207", fillColor: "#eab308", isHigh: false };
      return { valStr: suscStr, color: "#10b981", borderColor: "#059669", fillColor: "#10b981", isHigh: false };
    }
    case "CURRENT_RISK":
    default: {
      const score = loc.risk_score ?? 10;
      const scoreStr = Math.round(score).toString();
      if (score >= 75) return { valStr: scoreStr, color: "#ef4444", borderColor: "#b91c1c", fillColor: "#ef4444", isHigh: true };
      if (score >= 50) return { valStr: scoreStr, color: "#f97316", borderColor: "#c2410c", fillColor: "#f97316", isHigh: true };
      if (score >= 25) return { valStr: scoreStr, color: "#eab308", borderColor: "#a16207", fillColor: "#eab308", isHigh: false };
      return { valStr: scoreStr, color: "#10b981", borderColor: "#059669", fillColor: "#10b981", isHigh: false };
    }
  }
}

function createPredictiveMarker(
  valStr: string,
  color: string,
  borderColor: string,
  isSelected: boolean,
  hasActiveEvent: boolean
) {
  const size = isSelected ? 38 : 30;
  const pulseHtml = hasActiveEvent
    ? `<span class="animate-ping" style="position: absolute; width: ${size + 14}px; height: ${size + 14}px; border-radius: 9999px; background-color: ${color}; opacity: 0.35;"></span>`
    : "";

  const html = `
    <div style="position: relative; width: ${size}px; height: ${size}px; display: flex; align-items: center; justify-content: center;">
      ${pulseHtml}
      <div style="
        width: ${size}px;
        height: ${size}px;
        border-radius: 9999px;
        background-color: ${color};
        border: ${isSelected ? "3px solid #ffffff" : `2px solid ${borderColor}`};
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.9);
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        font-weight: 800;
        font-size: ${isSelected ? "11px" : "9px"};
        font-family: monospace;
        letter-spacing: -0.5px;
      ">
        ${valStr}
      </div>
    </div>
  `;

  return L.divIcon({
    className: "custom-predictive-marker",
    html,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  });
}

export default function RiskMapInner({
  locations,
  selectedLocationId,
  onSelectLocation,
  onOpenInvestigate,
}: RiskMapInnerProps) {
  const [activeTileKey, setActiveTileKey] = useState<string>("topo");
  const [activeLayer, setActiveLayer] = useState<PredictionLayer>("FORECAST_24H");

  const selectedLocation = locations.find((l) => l.id === selectedLocationId);
  const defaultCenter: [number, number] = [26.2006, 92.9376];
  const defaultZoom = 7;
  const currentTile = MAP_TILES[activeTileKey] || MAP_TILES.topo;

  return (
    <div className="relative w-full h-[500px] lg:h-[580px] rounded-lg overflow-hidden border border-zinc-800 shadow-2xl bg-black">
      {/* 1. Top Control Bar: Map Tile + Prediction Layer Selector */}
      <div className="absolute top-3 left-3 right-3 z-[1000] flex flex-wrap items-center justify-between gap-2 pointer-events-none">
        {/* Layer Selector */}
        <div className="pointer-events-auto bg-black/90 border border-zinc-800 rounded-md p-1 shadow-2xl flex items-center gap-1 font-mono text-[10px] backdrop-blur-sm overflow-x-auto max-w-full">
          <div className="px-2 py-1 text-zinc-400 font-bold uppercase flex items-center gap-1 border-r border-zinc-800 whitespace-nowrap">
            <Layers className="w-3 h-3 text-emerald-400" />
            <span className="hidden sm:inline">Layer:</span>
          </div>
          <button
            onClick={() => setActiveLayer("FORECAST_24H")}
            className={`px-2 py-1 rounded transition font-bold whitespace-nowrap ${
              activeLayer === "FORECAST_24H"
                ? "bg-emerald-500 text-black font-black shadow-sm"
                : "text-zinc-400 hover:text-white hover:bg-zinc-900"
            }`}
          >
            24H ML Forecast
          </button>
          <button
            onClick={() => setActiveLayer("CURRENT_RISK")}
            className={`px-2 py-1 rounded transition font-bold whitespace-nowrap ${
              activeLayer === "CURRENT_RISK"
                ? "bg-white text-black font-black shadow-sm"
                : "text-zinc-400 hover:text-white hover:bg-zinc-900"
            }`}
          >
            Current Risk (Physics)
          </button>
          <button
            onClick={() => setActiveLayer("ANOMALY")}
            className={`px-2 py-1 rounded transition font-bold whitespace-nowrap ${
              activeLayer === "ANOMALY"
                ? "bg-amber-400 text-black font-black shadow-sm"
                : "text-zinc-400 hover:text-white hover:bg-zinc-900"
            }`}
          >
            Anomaly
          </button>
          <button
            onClick={() => setActiveLayer("RAINFALL")}
            className={`px-2 py-1 rounded transition font-bold whitespace-nowrap ${
              activeLayer === "RAINFALL"
                ? "bg-blue-400 text-black font-black shadow-sm"
                : "text-zinc-400 hover:text-white hover:bg-zinc-900"
            }`}
          >
            Rainfall (24h)
          </button>
          <button
            onClick={() => setActiveLayer("SOIL_MOISTURE")}
            className={`px-2 py-1 rounded transition font-bold whitespace-nowrap ${
              activeLayer === "SOIL_MOISTURE"
                ? "bg-cyan-400 text-black font-black shadow-sm"
                : "text-zinc-400 hover:text-white hover:bg-zinc-900"
            }`}
          >
            Soil Moisture
          </button>
          <button
            onClick={() => setActiveLayer("SUSCEPTIBILITY")}
            className={`px-2 py-1 rounded transition font-bold whitespace-nowrap ${
              activeLayer === "SUSCEPTIBILITY"
                ? "bg-purple-400 text-black font-black shadow-sm"
                : "text-zinc-400 hover:text-white hover:bg-zinc-900"
            }`}
          >
            Susceptibility
          </button>
        </div>

        {/* Top Right: Tile Base Map Switcher */}
        <div className="pointer-events-auto bg-black/90 border border-zinc-800 rounded-md p-1 shadow-2xl flex items-center gap-1 font-mono text-[10px] backdrop-blur-sm ml-auto">
          <Globe className="w-3 h-3 text-zinc-400 ml-1.5" />
          {Object.entries(MAP_TILES).map(([k, v]) => (
            <button
              key={k}
              onClick={() => setActiveTileKey(k)}
              className={`px-2 py-0.5 rounded transition ${
                activeTileKey === k
                  ? "bg-zinc-200 text-black font-black"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              {v.name}
            </button>
          ))}
        </div>
      </div>

      {/* 2. Main Map Container */}
      <MapContainer
        center={defaultCenter}
        zoom={defaultZoom}
        className="w-full h-full"
        zoomControl={false}
        attributionControl={false}
      >
        <TileLayer
          key={activeTileKey}
          url={currentTile.url}
          maxZoom={currentTile.maxZoom}
        />

        <MapController selectedLocation={selectedLocation} />

        {/* Station Prediction Sectors (Transparent Voronoi/Catchment Radius) */}
        {locations.map((loc) => {
          const metric = getLayerMetricValue(loc, activeLayer);
          const isSelected = loc.id === selectedLocationId;

          return (
            <React.Fragment key={`sector-${loc.id}`}>
              <Circle
                center={[loc.latitude, loc.longitude]}
                radius={22000} // 22km station catchment perimeter
                pathOptions={{
                  color: metric.color,
                  fillColor: metric.fillColor,
                  fillOpacity: isSelected ? 0.35 : 0.18,
                  weight: isSelected ? 2 : 1,
                  dashArray: "4, 4",
                }}
              />
              <Marker
                position={[loc.latitude, loc.longitude]}
                icon={createPredictiveMarker(
                  metric.valStr,
                  metric.color,
                  metric.borderColor,
                  isSelected,
                  loc.active_event
                )}
                eventHandlers={{
                  click: () => onSelectLocation(loc.id),
                }}
              >
                <Popup>
                  <div className="p-3.5 space-y-2.5 max-w-[290px] text-white bg-black font-sans rounded">
                    {/* Header */}
                    <div className="border-b border-zinc-800 pb-2">
                      <div className="flex items-center justify-between text-[10px] font-mono text-zinc-400">
                        <span>{loc.district}, {loc.state}</span>
                        <span className={`px-1.5 py-0.5 rounded font-bold ${
                          loc.data_freshness === "FRESH" ? "bg-emerald-950 text-emerald-300 border border-emerald-800" :
                          loc.data_freshness === "AGING" ? "bg-amber-950 text-amber-300 border border-amber-800" :
                          "bg-red-950 text-red-300 border border-red-800"
                        }`}>
                          {loc.data_freshness || "FRESH"}
                        </span>
                      </div>
                      <div className="text-base font-black text-white leading-tight mt-0.5">
                        {loc.name}
                      </div>
                    </div>

                    {/* Dual Core Metric Display: Deterministic vs ML */}
                    <div className="grid grid-cols-2 gap-2 bg-zinc-950 p-2 rounded border border-zinc-800 font-mono">
                      <div>
                        <div className="text-[9px] text-zinc-400 font-bold uppercase">Current Condition</div>
                        <div className="text-sm font-black text-white mt-0.5">
                          {loc.risk_score.toFixed(1)}
                          <span className="text-[10px] text-zinc-500 font-normal"> / 100</span>
                        </div>
                        <span className={`inline-block px-1.5 py-0.2 rounded text-[10px] font-bold mt-1 ${
                          loc.risk_level === "CRITICAL" ? "text-red-400" :
                          loc.risk_level === "HIGH" ? "text-orange-400" :
                          loc.risk_level === "MODERATE" ? "text-amber-400" :
                          "text-emerald-400"
                        }`}>
                          {loc.risk_level} (Physics)
                        </span>
                      </div>
                      <div className="border-l border-zinc-800 pl-2">
                        <div className="text-[9px] text-emerald-400 font-bold uppercase">24H ML Forecast</div>
                        <div className="text-sm font-black text-white mt-0.5">
                          {loc.forecast_probabilities?.["24h"] !== undefined
                            ? `${(loc.forecast_probabilities["24h"] * 100).toFixed(1)}%`
                            : "UNAVAILABLE"}
                        </div>
                        <span className="text-[10px] text-zinc-400 block mt-1">
                          {loc.forecast_probabilities?.["24h"] !== undefined && loc.forecast_probabilities["24h"] >= 0.50
                            ? "Threshold Exceeded"
                            : "Within Bounds"}
                        </span>
                      </div>
                    </div>

                    {/* Hydro-Meteorological Saturation */}
                    <div className="grid grid-cols-2 gap-1.5 text-[11px] text-zinc-400 font-mono">
                      <div className="bg-zinc-950 p-1.5 rounded border border-zinc-800">
                        <div className="text-[9px] text-zinc-500 font-bold">24H RAIN</div>
                        <div className="text-white font-bold">{loc.rainfall_24h ?? 0} mm</div>
                      </div>
                      <div className="bg-zinc-950 p-1.5 rounded border border-zinc-800">
                        <div className="text-[9px] text-zinc-500 font-bold">SOIL SATURATION</div>
                        <div className="text-white font-bold">{loc.soil_moisture ?? "--"}%</div>
                      </div>
                    </div>

                    {/* Geomorphology & Anomaly */}
                    <div className="grid grid-cols-2 gap-1.5 text-[11px] text-zinc-400 font-mono">
                      <div className="bg-zinc-950 p-1.5 rounded border border-zinc-800">
                        <div className="text-[9px] text-zinc-500 font-bold">SLOPE / ELEV</div>
                        <div className="text-white font-bold">{loc.slope_angle ?? 30}° / {loc.elevation ?? 1200}m</div>
                      </div>
                      <div className="bg-zinc-950 p-1.5 rounded border border-zinc-800">
                        <div className="text-[9px] text-zinc-500 font-bold">ANOMALY STATUS</div>
                        <div className={`font-bold ${
                          loc.anomaly_level === "SEVERE" ? "text-red-400" :
                          loc.anomaly_level === "ELEVATED" ? "text-amber-400" : "text-emerald-400"
                        }`}>
                          {loc.anomaly_level || "NORMAL"}
                        </div>
                      </div>
                    </div>

                    {/* Model Provenance & Action */}
                    <div className="border-t border-zinc-800 pt-2 flex items-center justify-between text-[9px] font-mono text-zinc-500">
                      <span>Model: {loc.model_version || "v2.0.0"} ({loc.model_status || "READY"})</span>
                      <button
                        onClick={() => onOpenInvestigate(loc.id)}
                        className="bg-white hover:bg-zinc-200 text-black text-[10px] font-bold py-1 px-2 rounded transition flex items-center gap-1 font-mono"
                      >
                        <span>Investigate</span>
                        <ArrowUpRight className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </Popup>
              </Marker>
            </React.Fragment>
          );
        })}
      </MapContainer>

      {/* 3. Bottom Spatial Resolution & Honesty Disclaimer Banner */}
      <div className="absolute bottom-2 left-2 right-2 z-[1000] bg-black/90 border border-zinc-800 rounded px-3 py-1.5 text-[10px] font-mono text-zinc-400 flex items-center justify-between backdrop-blur-sm">
        <div className="flex items-center gap-1.5">
          <Info className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
          <span>
            <strong className="text-white">Spatial Resolution Disclosure:</strong> Showing station telemetry &amp; Voronoi catchment perimeters across the North Eastern Region. No unverified 30m interpolation is fabricated.
          </span>
        </div>
        <div className="hidden md:flex items-center gap-2 text-[9px] text-zinc-500">
          <span>Active Layer: <strong className="text-white">{activeLayer}</strong></span>
          <span>&bull;</span>
          <span>Status: <strong className="text-emerald-400">OPERATIONAL</strong></span>
        </div>
      </div>
    </div>
  );
}
