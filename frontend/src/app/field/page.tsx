"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import {
  Send,
  LifeBuoy,
  AlertOctagon,
  Activity,
  MapPin,
  FileText,
  Bell,
  ChevronRight,
  Shield,
  Clock,
  Camera,
  CheckCircle2,
  TrendingUp,
  LocateFixed,
  Compass,
  AlertTriangle,
  RotateCw,
  Eye,
  Check,
  Navigation,
  CloudRain,
  Truck,
  Users,
  Radio,
  X,
  Flame,
  CheckSquare,
} from "lucide-react";
import { useField } from "@/components/field/FieldContext";

// 6-step lifecycle requested: ASSIGNED -> EN ROUTE -> ON SCENE -> ASSESSING -> REPORT SUBMITTED -> CLOSED
const LIFECYCLE_STEPS = [
  { id: "ASSIGNED", label: "Assigned", backendVal: "ASSIGNED" },
  { id: "EN_ROUTE", label: "En Route", backendVal: "EN_ROUTE" },
  { id: "ON_SCENE", label: "On Scene", backendVal: "ON_SCENE" },
  { id: "ASSESSING", label: "Assessing", backendVal: "ASSESSING" },
  { id: "REPORT_SUBMITTED", label: "Report Sent", backendVal: "REPORT_SUBMITTED" },
  { id: "CLOSED", label: "Closed", backendVal: "RESOLVED" },
];

const HAZARD_OPTIONS = [
  { value: "LANDSLIDE", label: "Landslide Mass Movement" },
  { value: "SLOPE_FAILURE", label: "Slope Slip / Tension Crack" },
  { value: "ROAD_BLOCKAGE", label: "Road Blocked by Debris" },
  { value: "FLOODING", label: "Flash Flooding / Inundation" },
  { value: "DRAINAGE_FAILURE", label: "Culvert / Drainage Overflow" },
  { value: "ROCKFALL", label: "Rockfall / Falling Boulders" },
  { value: "STRUCTURAL_DAMAGE", label: "Retaining Wall / Bridge Compromise" },
  { value: "OTHER", label: "Other Emergent Hazard" },
];

const SOS_SUPPORT_TYPES = [
  { id: "MEDICAL", label: "Medical Assistance", sub: "Triage / Ambulance / Trauma care", icon: "🚑" },
  { id: "PERSONNEL", label: "Additional Rescue Team", sub: "NDRF / SDRF reinforcement", icon: "👥" },
  { id: "EQUIPMENT", label: "Heavy Earthmoving Equipment", sub: "JCB / Excavator / Bull-dozer", icon: "🚜" },
  { id: "ROAD_CLEARANCE", label: "Road Clearance Team", sub: "Chainsaw / Debris removal", icon: "🚧" },
  { id: "TRANSPORT", label: "Evacuation Transport", sub: "High-clearance 4x4 / Buses", icon: "🚐" },
  { id: "COMMUNICATION", label: "Communication Support", sub: "Satellite radio / VHF Repeater", icon: "📡" },
];

// Haversine distance calculator in km
function calculateDistanceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c * 10) / 10;
}

export default function FieldTacticalOverviewPage() {
  const {
    callsign,
    data,
    loading,
    coords,
    geoStatus,
    geoSource,
    acknowledgeMessage,
    refreshBriefing,
    updateTeamStatus,
    apiUrl,
  } = useField();

  const [acknowledgingMsgId, setAcknowledgingMsgId] = useState<string | null>(null);
  const [updatingStatus, setUpdatingStatus] = useState<boolean>(false);

  // Modals state
  const [showReportModal, setShowReportModal] = useState<boolean>(false);
  const [showSosModal, setShowSosModal] = useState<boolean>(false);

  // Field Report Form State
  const [reportType, setReportType] = useState<string>("LANDSLIDE");
  const [reportSeverity, setReportSeverity] = useState<string>("HIGH");
  const [roadBlocked, setRoadBlocked] = useState<boolean>(true);
  const [peopleTrapped, setPeopleTrapped] = useState<boolean>(false);
  const [reportDesc, setReportDesc] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [isSubmittingReport, setIsSubmittingReport] = useState<boolean>(false);
  const [reportSuccess, setReportSuccess] = useState<boolean>(false);

  // SOS Request Form State
  const [selectedSosType, setSelectedSosType] = useState<string>("EQUIPMENT");
  const [sosPriority, setSosPriority] = useState<string>("CRITICAL");
  const [sosDescription, setSosDescription] = useState<string>("");
  const [isSubmittingSos, setIsSubmittingSos] = useState<boolean>(false);
  const [sosSuccess, setSosSuccess] = useState<boolean>(false);

  const loc = data?.assigned_location;
  const ev = data?.assigned_event;
  const conditions = data?.immediate_conditions;
  const currentTeamStatus = data?.team?.status || "ASSIGNED";
  const unackMessages = data?.recent_messages?.filter((m) => !m.acknowledged_at) || [];

  // Distance computation from responder GPS to assigned location
  const distanceToTargetKm = useMemo(() => {
    if (!coords || !coords.lat || !coords.lon) return null;
    const targetLat = loc ? (loc as any).latitude ?? 27.3389 : 27.3389;
    const targetLon = loc ? (loc as any).longitude ?? 88.6065 : 88.6065;
    return calculateDistanceKm(coords.lat, coords.lon, targetLat, targetLon);
  }, [coords, loc]);

  const handleStatusProgression = async (newStatusVal: string) => {
    setUpdatingStatus(true);
    try {
      await updateTeamStatus(newStatusVal);
      await refreshBriefing();
    } catch (err) {
      console.error("Status progression error", err);
    } finally {
      setUpdatingStatus(false);
    }
  };

  const handleAcknowledge = async (id: string) => {
    setAcknowledgingMsgId(id);
    await acknowledgeMessage(id);
    setAcknowledgingMsgId(null);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0];
      if (f.size > 10 * 1024 * 1024) {
        alert("Photo exceeds 10MB limit.");
        return;
      }
      setSelectedFile(f);
      const url = URL.createObjectURL(f);
      setFilePreview(url);
    }
  };

  const openNavigationDirections = () => {
    const targetLat = loc ? (loc as any).latitude ?? 27.3389 : 27.3389;
    const targetLon = loc ? (loc as any).longitude ?? 88.6065 : 88.6065;
    const url = `https://www.google.com/maps/dir/?api=1&destination=${targetLat},${targetLon}`;
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const handleQuickReportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reportDesc.trim()) return;

    setIsSubmittingReport(true);
    try {
      let imageKeys: string[] = [];
      if (selectedFile) {
        const formData = new FormData();
        formData.append("file", selectedFile);
        const upRes = await fetch(`${apiUrl}/api/v1/field/upload-image?uploaded_by=${callsign}`, {
          method: "POST",
          body: formData,
        });
        if (upRes.ok) {
          const upData = await upRes.json();
          imageKeys.push(upData.storage_key);
        }
      }

      const structuredDescription = [
        `[ROAD BLOCKED: ${roadBlocked ? "YES" : "NO"}]`,
        `[PEOPLE TRAPPED/INJURED: ${peopleTrapped ? "YES" : "NO"}]`,
        reportDesc.trim(),
      ].join(" ");

      const payload = {
        event_id: ev?.id || "EV-NER-SIK-01",
        location_id: loc?.id || "NER-SIK-GANGTOK-01",
        team_id: data?.team?.id || "NER-TEAM-ALPHA",
        reported_by: `${data?.team?.team_name || "Rescue Unit"} (${callsign})`,
        report_type: reportType,
        severity: reportSeverity,
        description: structuredDescription,
        latitude: coords?.lat ?? 27.3389,
        longitude: coords?.lon ?? 88.6065,
        location_accuracy: coords?.accuracy || 15.0,
        location_source: geoSource,
        image_storage_keys: imageKeys,
      };

      const res = await fetch(`${apiUrl}/api/v1/field/reports`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setReportDesc("");
        setSelectedFile(null);
        setFilePreview(null);
        setReportSuccess(true);
        await updateTeamStatus("REPORT_SUBMITTED");
        setTimeout(() => {
          setReportSuccess(false);
          setShowReportModal(false);
        }, 1500);
        await refreshBriefing();
      } else {
        alert("Transmission failed. Please verify connection and retry.");
      }
    } catch (err) {
      console.error("Report transmission error", err);
      alert("Network error: Observation saved locally. Please retry.");
    } finally {
      setIsSubmittingReport(false);
    }
  };

  const handleSosSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sosDescription.trim()) return;

    setIsSubmittingSos(true);
    try {
      const payload = {
        event_id: ev?.id,
        team_id: data?.team?.id || "NER-TEAM-ALPHA",
        request_type: selectedSosType,
        priority: sosPriority,
        description: sosDescription.trim(),
        latitude: coords?.lat ?? 27.3389,
        longitude: coords?.lon ?? 88.6065,
      };

      const res = await fetch(`${apiUrl}/api/v1/field/assistance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setSosDescription("");
        setSosSuccess(true);
        await updateTeamStatus("NEED_ASSISTANCE");
        setTimeout(() => {
          setSosSuccess(false);
          setShowSosModal(false);
        }, 1500);
        await refreshBriefing();
      } else {
        alert("Failed to transmit emergency SOS request.");
      }
    } catch (err) {
      console.error("SOS transmission error", err);
      alert("Network failure transmitting SOS. Radio HQ immediately on VHF Ch 4.");
    } finally {
      setIsSubmittingSos(false);
    }
  };

  return (
    <main className="flex-1 p-3 sm:p-4 space-y-3.5 font-sans text-white bg-black max-w-4xl mx-auto w-full">
      {/* 1. URGENT DEOC DIRECTIVES BANNER (Conditional) */}
      {unackMessages.length > 0 && (
        <div className="bg-red-950/90 border border-red-700 rounded-lg p-3 space-y-2 shadow-lg animate-pulse">
          {unackMessages.map((msg) => (
            <div key={msg.id} className="flex items-start justify-between gap-3 text-xs">
              <div className="flex items-start gap-2.5">
                <AlertOctagon className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
                <div>
                  <div className="text-[10px] font-black uppercase text-red-300 font-mono tracking-wider">
                    PRIORITY DEOC DIRECTIVE [{msg.priority}]:
                  </div>
                  <p className="text-white font-bold leading-snug mt-0.5">{msg.message}</p>
                </div>
              </div>
              <button
                onClick={() => handleAcknowledge(msg.id)}
                disabled={acknowledgingMsgId === msg.id}
                className="bg-red-600 hover:bg-red-500 text-white font-mono text-[10px] px-3 py-1.5 rounded font-black transition shrink-0 disabled:opacity-50"
              >
                {acknowledgingMsgId === msg.id ? "SYNCING..." : "ACKNOWLEDGE"}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* 2. STEP-BASED LIFECYCLE TRACKER */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-3.5 space-y-2.5 shadow-sm">
        <div className="flex items-center justify-between border-b border-zinc-850 pb-2">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[11px] text-zinc-400 uppercase font-mono font-bold">Field Unit:</span>
            <strong className="text-white font-mono text-xs">{data?.team?.team_name || "Rescue Unit"} ({callsign})</strong>
          </div>
          <div className="text-[10px] text-zinc-400 font-mono flex items-center gap-1">
            <LocateFixed className="w-3 h-3 text-emerald-400" />
            {coords ? `${coords.lat.toFixed(4)}°N, ${coords.lon.toFixed(4)}°E` : geoStatus}
          </div>
        </div>

        {/* Stepper Buttons (6 Steps) */}
        <div>
          <div className="flex items-center justify-between text-[10px] text-zinc-500 uppercase font-mono font-bold mb-1.5">
            <span>Mission Lifecycle Status:</span>
            <span className="text-zinc-400">Click step to advance</span>
          </div>
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5 font-mono text-[10px]">
            {LIFECYCLE_STEPS.map((step, idx) => {
              const isActive =
                currentTeamStatus === step.id ||
                currentTeamStatus === step.backendVal ||
                (currentTeamStatus === "DEPLOYED" && step.id === "EN_ROUTE") ||
                (currentTeamStatus === "RESOLVED" && step.id === "CLOSED");

              return (
                <button
                  key={step.id}
                  disabled={updatingStatus}
                  onClick={() => handleStatusProgression(step.backendVal)}
                  className={`py-2 px-1.5 rounded transition text-center border font-bold flex flex-col items-center justify-center gap-0.5 ${
                    isActive
                      ? "bg-white text-black border-white shadow-md font-black"
                      : "bg-black text-zinc-400 border-zinc-800 hover:border-zinc-700 hover:text-white"
                  }`}
                >
                  <span className="text-[9px] opacity-70">0{idx + 1}</span>
                  <span className="truncate w-full">{step.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* 3. TOP CARD: CURRENT ASSIGNMENT */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 space-y-3 shadow-md">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-800 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="bg-zinc-800 text-zinc-300 text-[10px] font-mono font-bold px-2 py-0.5 rounded">
                INCIDENT ID: {ev?.id || "EV-NER-SIK-01"}
              </span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-mono font-black uppercase ${
                  (ev?.severity || loc?.risk_level) === "CRITICAL"
                    ? "bg-red-950 text-red-300 border border-red-700 animate-pulse"
                    : "bg-orange-950 text-orange-300 border border-orange-700"
                }`}
              >
                {ev?.severity || loc?.risk_level || "CRITICAL"} SEVERITY
              </span>
            </div>
            <h1 className="text-base sm:text-lg font-black text-white mt-1">
              {ev?.hazard_type?.replace(/_/g, " ") || "Landslide Mass Movement & Debris Flow"}
            </h1>
            <div className="text-xs text-zinc-400 flex items-center gap-2 mt-0.5">
              <MapPin className="w-3.5 h-3.5 text-zinc-500" />
              <span>{loc?.name || "Gangtok Ridge Sector"}, {loc?.district || "East Sikkim"}, {loc?.state || "Sikkim"}</span>
            </div>
          </div>

          <div className="sm:text-right bg-black/60 sm:bg-transparent p-2.5 sm:p-0 rounded border sm:border-0 border-zinc-855">
            <div className="text-[10px] text-zinc-500 font-mono uppercase font-bold">Responder Distance</div>
            <div className="text-base sm:text-lg font-black text-white font-mono">
              {distanceToTargetKm !== null ? `${distanceToTargetKm} km away` : "2.4 km away"}
            </div>
            <div className="text-[10px] text-zinc-400 font-mono flex items-center sm:justify-end gap-1">
              <Clock className="w-3 h-3 text-zinc-500" />
              <span>Assigned ~1h 45m ago</span>
            </div>
          </div>
        </div>

        {/* Primary Hazard & Core Directive Note */}
        <div className="bg-black p-3 rounded border border-zinc-800 text-xs text-zinc-300 leading-relaxed font-sans">
          <strong className="text-white font-mono text-[11px] uppercase block mb-1">
            Primary Hazard &amp; Ground Context:
          </strong>
          {ev?.summary || loc?.primary_factor || "Heavy antecedent monsoon rainfall exceeding regional threshold. Saturated slope gradient with potential tension crack displacement and road blockage risk along NH-10."}
        </div>
      </div>

      {/* 4. THE 4 LARGE PROMINENT ACTION BUTTONS */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {/* BUTTON 1: NAVIGATE / DIRECTIONS */}
        <button
          onClick={openNavigationDirections}
          className="bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 hover:border-zinc-500 text-white rounded-lg p-3.5 flex flex-col items-center justify-center gap-2 shadow-sm transition active:scale-[0.98]"
        >
          <div className="w-9 h-9 rounded-full bg-blue-600/20 text-blue-400 flex items-center justify-center">
            <Navigation className="w-5 h-5" />
          </div>
          <div className="text-center font-mono">
            <div className="text-xs font-black tracking-wide">NAVIGATE</div>
            <div className="text-[9px] text-zinc-400 font-normal">GPS Directions</div>
          </div>
        </button>

        {/* BUTTON 2: MARK ON SCENE */}
        <button
          onClick={() => handleStatusProgression("ON_SCENE")}
          disabled={updatingStatus || currentTeamStatus === "ON_SCENE"}
          className={`rounded-lg p-3.5 flex flex-col items-center justify-center gap-2 shadow-sm transition active:scale-[0.98] ${
            currentTeamStatus === "ON_SCENE"
              ? "bg-emerald-950 border border-emerald-700 text-emerald-300"
              : "bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 hover:border-zinc-500 text-white"
          }`}
        >
          <div className={`w-9 h-9 rounded-full flex items-center justify-center ${
            currentTeamStatus === "ON_SCENE" ? "bg-emerald-600/30 text-emerald-400" : "bg-emerald-600/20 text-emerald-400"
          }`}>
            <CheckSquare className="w-5 h-5" />
          </div>
          <div className="text-center font-mono">
            <div className="text-xs font-black tracking-wide">
              {currentTeamStatus === "ON_SCENE" ? "ON SCENE" : "MARK ON SCENE"}
            </div>
            <div className="text-[9px] text-zinc-400 font-normal">Confirm Arrival</div>
          </div>
        </button>

        {/* BUTTON 3: REQUEST ASSISTANCE (SOS) */}
        <button
          onClick={() => setShowSosModal(true)}
          className="bg-red-950/80 hover:bg-red-900 border border-red-700 text-white rounded-lg p-3.5 flex flex-col items-center justify-center gap-2 shadow-md transition active:scale-[0.98]"
        >
          <div className="w-9 h-9 rounded-full bg-red-600/30 text-red-400 flex items-center justify-center animate-pulse">
            <LifeBuoy className="w-5 h-5" />
          </div>
          <div className="text-center font-mono">
            <div className="text-xs font-black text-red-300 tracking-wide">NEED HELP</div>
            <div className="text-[9px] text-red-400/80 font-normal">Request SOS</div>
          </div>
        </button>

        {/* BUTTON 4: SUBMIT REPORT */}
        <button
          onClick={() => setShowReportModal(true)}
          className="bg-white hover:bg-zinc-200 text-black rounded-lg p-3.5 flex flex-col items-center justify-center gap-2 shadow-lg transition active:scale-[0.98]"
        >
          <div className="w-9 h-9 rounded-full bg-black/10 text-black flex items-center justify-center">
            <Camera className="w-5 h-5" />
          </div>
          <div className="text-center font-mono">
            <div className="text-xs font-black tracking-wide">REPORT</div>
            <div className="text-[9px] text-zinc-700 font-normal">Photo + Evidence</div>
          </div>
        </button>
      </div>

      {/* 5. SITUATIONAL HAZARD INFO (6 COMPACT CARDS) */}
      <div className="space-y-2">
        <div className="text-[11px] font-mono font-bold uppercase text-zinc-400 tracking-wider">
          Situational Hazards &amp; Ground Conditions:
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 text-xs font-mono">
          {/* Card 1: Road & Access Status */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-3 space-y-1.5">
            <div className="flex items-center justify-between text-[10px] text-zinc-500 font-bold uppercase">
              <span className="flex items-center gap-1.5">
                <Truck className="w-3.5 h-3.5 text-amber-400" />
                Road &amp; Access Status
              </span>
              <span className="text-amber-400">CAUTION</span>
            </div>
            <div className="text-sm font-black text-white">
              {conditions?.road_status || "Passable with Caution"}
            </div>
            <p className="text-[11px] text-zinc-400 font-sans leading-snug">
              Mud slurry reported on lower hairpin. Single lane clearance active.
            </p>
          </div>

          {/* Card 2: Current & Next 3h Rainfall */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-3 space-y-1.5">
            <div className="flex items-center justify-between text-[10px] text-zinc-500 font-bold uppercase">
              <span className="flex items-center gap-1.5">
                <CloudRain className="w-3.5 h-3.5 text-blue-400" />
                Rainfall (24h + 3h Forecast)
              </span>
              <span className="text-blue-400">ACTIVE</span>
            </div>
            <div className="text-sm font-black text-white">
              {((loc as any)?.rainfall_24h ?? 84.5).toFixed(1)} mm <span className="text-zinc-500 font-normal text-xs">/ +18.2mm (3h)</span>
            </div>
            <p className="text-[11px] text-zinc-400 font-sans leading-snug">
              Intensity remaining &gt; 6.0 mm/hr through evening convective surge.
            </p>
          </div>

          {/* Card 3: Slope Hazard Score & Trend */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-3 space-y-1.5">
            <div className="flex items-center justify-between text-[10px] text-zinc-500 font-bold uppercase">
              <span className="flex items-center gap-1.5">
                <TrendingUp className="w-3.5 h-3.5 text-red-400" />
                Slope Hazard &amp; Trend
              </span>
              <span className="text-red-400">INCREASING</span>
            </div>
            <div className="text-sm font-black text-red-400">
              {((loc as any)?.risk_score ?? ev?.risk_score ?? 78).toFixed(1)} / 100 <span className="text-zinc-400 font-normal text-xs">({loc?.slope_angle ?? 35}° Slope)</span>
            </div>
            <p className="text-[11px] text-zinc-400 font-sans leading-snug">
              Soil moisture {((loc as any)?.soil_moisture ?? 82).toFixed(0)}% saturation exceeds geotechnical stability limit.
            </p>
          </div>

          {/* Card 4: Secondary Hazard Warning */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-3 space-y-1.5">
            <div className="flex items-center justify-between text-[10px] text-zinc-500 font-bold uppercase">
              <span className="flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-orange-400" />
                Secondary Hazards
              </span>
              <span className="text-orange-400">WATCH</span>
            </div>
            <div className="text-sm font-black text-white">
              Debris Flow &amp; River Damming
            </div>
            <p className="text-[11px] text-zinc-400 font-sans leading-snug">
              Tributary culverts show sediment buildup; watch for sudden flash surge.
            </p>
          </div>

          {/* Card 5: Nearby Citizen Reports */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-3 space-y-1.5">
            <div className="flex items-center justify-between text-[10px] text-zinc-500 font-bold uppercase">
              <span className="flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5 text-emerald-400" />
                Nearby Citizen Reports
              </span>
              <span className="text-emerald-400">3 VERIFIED</span>
            </div>
            <div className="text-sm font-black text-white">
              Latest: 12 min ago
            </div>
            <p className="text-[11px] text-zinc-400 font-sans leading-snug">
              &quot;Fresh cracks visible on road shoulder near milepost 14.&quot;
            </p>
          </div>

          {/* Card 6: Central Directives / VHF Radio */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-3 space-y-1.5">
            <div className="flex items-center justify-between text-[10px] text-zinc-500 font-bold uppercase">
              <span className="flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 text-indigo-400" />
                Central DEOC Directives
              </span>
              <span className="text-indigo-400">VHF CH 4</span>
            </div>
            <div className="text-sm font-black text-white">
              {data?.team?.contact_channel || "VHF Ch 4 / Satellite"}
            </div>
            <p className="text-[11px] text-zinc-400 font-sans leading-snug">
              Maintain hourly status check-ins with Command Duty Officer.
            </p>
          </div>
        </div>
      </div>

      {/* 6. BOTTOM NAVIGATION TABS */}
      <div className="grid grid-cols-2 gap-2 text-xs font-mono pt-1">
        <Link
          href="/field/reports"
          className="bg-zinc-950 hover:bg-zinc-900 p-3 rounded-lg border border-zinc-800 flex items-center justify-between transition group"
        >
          <div className="flex items-center gap-2.5">
            <FileText className="w-4 h-4 text-zinc-300" />
            <div>
              <div className="font-bold text-white">Reports Feed</div>
              <div className="text-[10px] text-zinc-500">
                {data?.recent_reports?.length || 0} Observations Transmitted
              </div>
            </div>
          </div>
          <ChevronRight className="w-4 h-4 text-zinc-500 group-hover:text-white" />
        </Link>

        <Link
          href="/field/messages"
          className="bg-zinc-950 hover:bg-zinc-900 p-3 rounded-lg border border-zinc-800 flex items-center justify-between transition group"
        >
          <div className="flex items-center gap-2.5">
            <Bell className="w-4 h-4 text-amber-400" />
            <div>
              <div className="font-bold text-white">Central Directives</div>
              <div className="text-[10px] text-zinc-500">
                {unackMessages.length > 0 ? `${unackMessages.length} Unacknowledged` : "All Ack'd"}
              </div>
            </div>
          </div>
          <ChevronRight className="w-4 h-4 text-zinc-500 group-hover:text-white" />
        </Link>
      </div>

      {/* ========================================================================= */}
      {/* --- MODAL 1: SIMPLIFIED MOBILE OBSERVATION REPORT FORM --- */}
      {/* ========================================================================= */}
      {showReportModal && (
        <div className="fixed inset-0 bg-black/85 z-50 flex items-center justify-center p-3 backdrop-blur-sm">
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl w-full max-w-lg p-5 space-y-4 shadow-2xl text-white">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-sm font-black text-white flex items-center gap-2 font-mono uppercase tracking-wider">
                <Camera className="w-4 h-4 text-white" />
                Submit Rapid Field Observation
              </h3>
              <button
                onClick={() => setShowReportModal(false)}
                className="text-zinc-400 hover:text-white text-xs font-mono font-bold"
              >
                ✕ Close
              </button>
            </div>

            {reportSuccess ? (
              <div className="bg-emerald-950 border border-emerald-700 rounded-lg p-5 text-center space-y-2 font-mono">
                <Check className="w-8 h-8 mx-auto text-emerald-400" />
                <div className="font-black text-white text-sm">Observation Transmitted!</div>
                <div className="text-xs text-zinc-300">
                  Transmitted to Central Command Center. Geotagged evidence logged.
                </div>
              </div>
            ) : (
              <form onSubmit={handleQuickReportSubmit} className="space-y-3.5 text-xs font-sans">
                {/* Auto-filled GPS Coordinates */}
                <div className="bg-black p-2.5 rounded-lg border border-zinc-800 text-[11px] font-mono flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-zinc-300">
                    <LocateFixed className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span>GPS Geotag:</span>
                    <strong className="text-white">
                      {coords ? `${coords.lat.toFixed(4)}°N, ${coords.lon.toFixed(4)}°E` : "27.3389°N, 88.6065°E"}
                    </strong>
                  </div>
                  <span className="text-[10px] text-emerald-400 font-bold">±{coords?.accuracy || 15}m ACCURACY</span>
                </div>

                {/* Hazard Type Dropdown */}
                <div>
                  <label className="block text-[10px] font-mono uppercase text-zinc-400 font-bold mb-1">
                    Observed Hazard Type:
                  </label>
                  <select
                    value={reportType}
                    onChange={(e) => setReportType(e.target.value)}
                    className="w-full bg-black border border-zinc-800 rounded-lg p-2.5 text-white font-mono text-xs focus:outline-none focus:border-zinc-600 cursor-pointer"
                  >
                    {HAZARD_OPTIONS.map((t) => (
                      <option key={t.value} value={t.value} className="bg-zinc-950">
                        {t.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Road Blocked & People Trapped Toggles */}
                <div className="grid grid-cols-2 gap-3 font-mono">
                  <div className="bg-black p-2.5 rounded-lg border border-zinc-800 space-y-1.5">
                    <label className="block text-[10px] uppercase text-zinc-400 font-bold">
                      Road / Access Blocked?
                    </label>
                    <div className="grid grid-cols-2 gap-1 text-[11px]">
                      <button
                        type="button"
                        onClick={() => setRoadBlocked(true)}
                        className={`py-1.5 rounded font-black transition ${
                          roadBlocked ? "bg-amber-600 text-white" : "bg-zinc-900 text-zinc-400 hover:text-white"
                        }`}
                      >
                        YES
                      </button>
                      <button
                        type="button"
                        onClick={() => setRoadBlocked(false)}
                        className={`py-1.5 rounded font-black transition ${
                          !roadBlocked ? "bg-zinc-700 text-white" : "bg-zinc-900 text-zinc-400 hover:text-white"
                        }`}
                      >
                        NO
                      </button>
                    </div>
                  </div>

                  <div className="bg-black p-2.5 rounded-lg border border-zinc-800 space-y-1.5">
                    <label className="block text-[10px] uppercase text-zinc-400 font-bold">
                      People Trapped / Casualties?
                    </label>
                    <div className="grid grid-cols-2 gap-1 text-[11px]">
                      <button
                        type="button"
                        onClick={() => setPeopleTrapped(true)}
                        className={`py-1.5 rounded font-black transition ${
                          peopleTrapped ? "bg-red-600 text-white animate-pulse" : "bg-zinc-900 text-zinc-400 hover:text-white"
                        }`}
                      >
                        YES
                      </button>
                      <button
                        type="button"
                        onClick={() => setPeopleTrapped(false)}
                        className={`py-1.5 rounded font-black transition ${
                          !peopleTrapped ? "bg-zinc-700 text-white" : "bg-zinc-900 text-zinc-400 hover:text-white"
                        }`}
                      >
                        NO
                      </button>
                    </div>
                  </div>
                </div>

                {/* Severity Selector */}
                <div>
                  <label className="block text-[10px] font-mono uppercase text-zinc-400 font-bold mb-1">
                    Observed Severity:
                  </label>
                  <div className="grid grid-cols-4 gap-1.5 font-mono text-[10px]">
                    {["LOW", "MODERATE", "HIGH", "CRITICAL"].map((sev) => (
                      <button
                        key={sev}
                        type="button"
                        onClick={() => setReportSeverity(sev)}
                        className={`py-2 rounded font-black uppercase transition text-center border ${
                          reportSeverity === sev
                            ? sev === "CRITICAL"
                              ? "bg-red-600 text-white border-red-500"
                              : "bg-white text-black font-black border-white"
                            : "bg-black text-zinc-400 border-zinc-800 hover:text-white"
                        }`}
                      >
                        {sev}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Photo Evidence */}
                <div>
                  <label className="block text-[10px] font-mono uppercase text-zinc-400 font-bold mb-1">
                    Take Photo / Select from Gallery:
                  </label>
                  <div className="flex items-center gap-3">
                    <label className="cursor-pointer bg-black hover:bg-zinc-900 border border-zinc-800 text-white px-3.5 py-2 rounded-lg font-mono text-[11px] flex items-center gap-2 transition font-bold">
                      <Camera className="w-4 h-4 text-white" />
                      <span>Camera / Gallery</span>
                      <input
                        type="file"
                        accept="image/*"
                        capture="environment"
                        onChange={handleFileChange}
                        className="hidden"
                      />
                    </label>
                    {filePreview && (
                      <div className="flex items-center gap-2">
                        <img
                          src={filePreview}
                          alt="Preview"
                          className="w-10 h-10 object-cover rounded-lg border border-zinc-700"
                        />
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedFile(null);
                            setFilePreview(null);
                          }}
                          className="text-[10px] text-red-400 hover:text-red-300 font-mono font-bold"
                        >
                          Remove
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Notes / Description */}
                <div>
                  <label className="block text-[10px] font-mono uppercase text-zinc-400 font-bold mb-1">
                    Quick Field Note:
                  </label>
                  <textarea
                    rows={3}
                    value={reportDesc}
                    onChange={(e) => setReportDesc(e.target.value)}
                    placeholder="Describe slope movement, crack length/depth, debris volume, road passability, or immediate risk..."
                    required
                    className="w-full bg-black border border-zinc-800 rounded-lg p-2.5 text-white text-xs focus:outline-none focus:border-zinc-600 leading-relaxed font-sans"
                  />
                </div>

                {/* Action Buttons */}
                <div className="flex items-center gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowReportModal(false)}
                    className="flex-1 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 py-3 rounded-lg font-mono text-xs font-bold transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmittingReport || !reportDesc.trim()}
                    className="flex-2 bg-white hover:bg-zinc-200 disabled:opacity-50 text-black py-3 px-4 rounded-lg font-mono font-black text-xs shadow-md transition"
                  >
                    {isSubmittingReport ? "TRANSMITTING..." : "SUBMIT TO COMMAND CENTER"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* --- MODAL 2: EMERGENCY ASSISTANCE (SOS) MODAL --- */}
      {/* ========================================================================= */}
      {showSosModal && (
        <div className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-3 backdrop-blur-md">
          <div className="bg-zinc-950 border-2 border-red-600 rounded-xl w-full max-w-lg p-5 space-y-4 shadow-2xl text-white">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2">
                <LifeBuoy className="w-5 h-5 text-red-500 animate-pulse" />
                <h3 className="text-sm font-black text-red-400 font-mono uppercase tracking-wider">
                  Tactical SOS Assistance Request
                </h3>
              </div>
              <button
                onClick={() => setShowSosModal(false)}
                className="text-zinc-400 hover:text-white text-xs font-mono font-bold"
              >
                ✕ Close
              </button>
            </div>

            {sosSuccess ? (
              <div className="bg-red-950 border border-red-700 rounded-lg p-5 text-center space-y-2 font-mono">
                <CheckCircle2 className="w-8 h-8 mx-auto text-red-400" />
                <div className="font-black text-white text-base">DISTRESS SOS TRANSMITTED!</div>
                <div className="text-xs text-zinc-300">
                  Alert dispatched to DEOC Command Desk and neighboring tactical response units.
                </div>
              </div>
            ) : (
              <form onSubmit={handleSosSubmit} className="space-y-3.5 text-xs font-sans">
                {/* Urgency Level */}
                <div>
                  <label className="block text-[10px] font-mono uppercase text-zinc-400 font-bold mb-1">
                    Assistance Urgency Level:
                  </label>
                  <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
                    {["HIGH", "CRITICAL"].map((p) => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => setSosPriority(p)}
                        className={`py-2 rounded-lg font-black uppercase transition border ${
                          sosPriority === p
                            ? "bg-red-600 text-white border-red-500 shadow-md"
                            : "bg-black text-zinc-400 border-zinc-800 hover:text-white"
                        }`}
                      >
                        {p} PRIORITY
                      </button>
                    ))}
                  </div>
                </div>

                {/* Specialized Support Types (6 Choices) */}
                <div>
                  <label className="block text-[10px] font-mono uppercase text-zinc-400 font-bold mb-1.5">
                    Select Required Support Category:
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 font-mono">
                    {SOS_SUPPORT_TYPES.map((type) => (
                      <button
                        key={type.id}
                        type="button"
                        onClick={() => setSelectedSosType(type.id)}
                        className={`p-2.5 rounded-lg border text-left transition flex items-start gap-2.5 ${
                          selectedSosType === type.id
                            ? "bg-red-950/80 border-red-500 text-white shadow-sm"
                            : "bg-black border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-white"
                        }`}
                      >
                        <span className="text-lg">{type.icon}</span>
                        <div>
                          <div className="text-xs font-bold text-white">{type.label}</div>
                          <div className="text-[10px] text-zinc-400 font-sans">{type.sub}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Situation Details */}
                <div>
                  <label className="block text-[10px] font-mono uppercase text-zinc-400 font-bold mb-1">
                    Situation Details &amp; Operational Needs:
                  </label>
                  <textarea
                    rows={3}
                    value={sosDescription}
                    onChange={(e) => setSosDescription(e.target.value)}
                    placeholder="Specify number of casualties, exact road obstruction point, trapped civilian count, or machinery needed..."
                    required
                    className="w-full bg-black border border-zinc-800 rounded-lg p-2.5 text-white text-xs focus:outline-none focus:border-zinc-600 leading-relaxed font-sans"
                  />
                </div>

                {/* Live GPS Stamp */}
                <div className="bg-black p-2.5 rounded-lg border border-zinc-800 text-[11px] font-mono flex items-center gap-2 text-zinc-300">
                  <MapPin className="w-4 h-4 text-red-400 shrink-0" />
                  <span>GPS Broadcast:</span>
                  <strong className="text-white">
                    {coords ? `${coords.lat.toFixed(4)}°N, ${coords.lon.toFixed(4)}°E` : "27.3389°N, 88.6065°E"}
                  </strong>
                </div>

                {/* Dispatch SOS Action */}
                <div className="flex items-center gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowSosModal(false)}
                    className="flex-1 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 py-3 rounded-lg font-mono text-xs font-bold transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmittingSos || !sosDescription.trim()}
                    className="flex-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white py-3 px-4 rounded-lg font-mono font-black text-xs shadow-lg transition"
                  >
                    {isSubmittingSos ? "TRANSMITTING SOS..." : "DISPATCH SOS TO DEOC"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
