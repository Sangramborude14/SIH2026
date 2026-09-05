"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Camera,
  Upload,
  CheckCircle2,
  Clock,
  MapPin,
  FileText,
  AlertTriangle,
  Info,
  Send,
  RefreshCw,
  X,
  ShieldCheck,
  WifiOff,
} from "lucide-react";
import {
  compressImageClientSide,
  queueOfflineReport,
  getPendingReports,
} from "@/lib/citizenOfflineStorage";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ReportItem {
  id: string;
  report_number: string;
  category: string;
  description: string;
  latitude?: number | null;
  longitude?: number | null;
  location_name?: string | null;
  photo_url?: string | null;
  status: string; // RECEIVED, UNDER_REVIEW, VERIFIED, REJECTED, DUPLICATE
  review_notes?: string | null;
  created_at: string;
}

const CATEGORIES = [
  { id: "GROUND_CRACK", label: "Ground Crack / Fissure", icon: "⚡" },
  { id: "ROCKFALL", label: "Rockfall on Road", icon: "🪨" },
  { id: "MUD_FLOW", label: "Mud / Debris Runoff", icon: "🌊" },
  { id: "LEANING_TREE_POLE", label: "Leaning Tree or Pole", icon: "🌲" },
  { id: "BLOCKED_ROAD_DRAIN", label: "Blocked Drain / Jhora", icon: "🚧" },
  { id: "RUMBLING_SOUND", label: "Rumbling Sounds in Hill", icon: "🔊" },
  { id: "OTHER", label: "Other Hazard", icon: "⚠️" },
];

export default function CitizenReportPage() {
  const [activeTab, setActiveTab] = useState<"NEW" | "HISTORY">("NEW");
  const [category, setCategory] = useState<string>("GROUND_CRACK");
  const [description, setDescription] = useState<string>("");
  const [landmark, setLandmark] = useState<string>("");
  const [contactPhone, setContactPhone] = useState<string>("");
  const [coords, setCoords] = useState<{ lat: number; lon: number; acc?: number } | null>(null);
  const [locStatus, setLocStatus] = useState<string>("Locating via GPS...");
  
  // Media states
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [compressedFile, setCompressedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [base64Image, setBase64Image] = useState<string | null>(null);
  const [compressionInfo, setCompressionInfo] = useState<string | null>(null);
  const [isCompressing, setIsCompressing] = useState<boolean>(false);

  const [submitting, setSubmitting] = useState<boolean>(false);
  const [successReport, setSuccessReport] = useState<ReportItem | null>(null);
  const [reportsList, setReportsList] = useState<ReportItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);

  // Auto-acquire GPS
  const captureGPS = useCallback(() => {
    if (typeof window !== "undefined" && "geolocation" in navigator) {
      setLocStatus("Acquiring GPS...");
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setCoords({
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            acc: pos.coords.accuracy ? Math.round(pos.coords.accuracy) : undefined,
          });
          setLocStatus(`GPS Acquired (±${Math.round(pos.coords.accuracy || 10)}m)`);
        },
        (err) => {
          setLocStatus("GPS unavailable. Please type landmark below.");
          setCoords({ lat: 27.3389, lon: 88.6065 });
        },
        { enableHighAccuracy: true, timeout: 8000 }
      );
    }
  }, []);

  useEffect(() => {
    captureGPS();
  }, [captureGPS]);

  // Load Submitted Reports History
  const loadReportsHistory = async () => {
    setLoadingHistory(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/citizen/reports?limit=20`);
      if (res.ok) {
        const data: ReportItem[] = await res.json();
        setReportsList(data);
      }
    } catch (err) {
      console.warn("Could not load reports history", err);
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    if (activeTab === "HISTORY") {
      loadReportsHistory();
    }
  }, [activeTab]);

  // Handle Image Selection and Client-side Canvas Downsampling
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setIsCompressing(true);
      const res = await compressImageClientSide(file, 1280, 0.75);
      setCompressedFile(res.compressedFile);
      setPreviewUrl(res.previewUrl);
      setCompressionInfo(`⚡ Reduced by ${res.sizeReductionPct}% (Clean EXIF stripped)`);

      // Read as base64 for offline fallback storage
      const reader = new FileReader();
      reader.onloadend = () => {
        setBase64Image(reader.result as string);
      };
      reader.readAsDataURL(res.compressedFile);
    } catch (err) {
      console.error("Image compression error:", err);
      alert("Failed to process photo. Please try a different image.");
    } finally {
      setIsCompressing(false);
    }
  };

  const clearPhoto = () => {
    setCompressedFile(null);
    setPreviewUrl(null);
    setBase64Image(null);
    setCompressionInfo(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // Submit Report
  const handleSubmitReport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim()) {
      alert("Please enter a short description of the observed hazard.");
      return;
    }

    setSubmitting(true);

    const reportData = {
      category,
      description: description.trim(),
      latitude: coords?.lat,
      longitude: coords?.lon,
      location_accuracy: coords?.acc,
      location_name: landmark.trim() || undefined,
      contact_phone: contactPhone.trim() || undefined,
      imageBase64: base64Image || undefined,
      imageFileName: compressedFile?.name,
      imageMimeType: compressedFile?.type,
    };

    // If offline, queue locally with "PENDING — WAITING FOR NETWORK"
    if (typeof window !== "undefined" && !navigator.onLine) {
      const queued = queueOfflineReport(reportData);
      setSuccessReport({
        id: queued.id,
        report_number: "OFFLINE-QUEUED",
        category,
        description,
        status: "PENDING_NETWORK",
        created_at: new Date().toISOString(),
      });
      setSubmitting(false);
      return;
    }

    try {
      const formData = new FormData();
      formData.append("category", category);
      formData.append("description", description.trim());
      if (coords?.lat) formData.append("latitude", coords.lat.toString());
      if (coords?.lon) formData.append("longitude", coords.lon.toString());
      if (coords?.acc) formData.append("location_accuracy", coords.acc.toString());
      if (landmark.trim()) formData.append("location_name", landmark.trim());
      if (contactPhone.trim()) formData.append("contact_phone", contactPhone.trim());

      if (compressedFile) {
        formData.append("photo", compressedFile, compressedFile.name);
      }

      const res = await fetch(`${API_URL}/api/v1/citizen/report`, {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        const created: ReportItem = await res.json();
        setSuccessReport(created);
        // Reset form
        setDescription("");
        setLandmark("");
        clearPhoto();
      } else {
        throw new Error("Server rejected report upload");
      }
    } catch (err) {
      console.warn("Failed to upload report, queueing locally:", err);
      const queued = queueOfflineReport(reportData);
      setSuccessReport({
        id: queued.id,
        report_number: "OFFLINE-QUEUED",
        category,
        description,
        status: "PENDING_NETWORK",
        created_at: new Date().toISOString(),
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-4 space-y-4">
      {/* Tab Switcher */}
      <div className="grid grid-cols-2 bg-slate-900 p-1 rounded-2xl border border-slate-800 text-xs font-bold font-mono">
        <button
          type="button"
          onClick={() => {
            setActiveTab("NEW");
            setSuccessReport(null);
          }}
          className={`py-2 rounded-xl transition ${
            activeTab === "NEW"
              ? "bg-slate-800 text-white shadow"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          Submit Observation
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("HISTORY")}
          className={`py-2 rounded-xl transition ${
            activeTab === "HISTORY"
              ? "bg-slate-800 text-white shadow"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          Recent Reports
        </button>
      </div>

      {/* TAB 1: NEW REPORT */}
      {activeTab === "NEW" && (
        <>
          {successReport ? (
            <div className="bg-slate-900 border-2 border-emerald-600 rounded-3xl p-6 shadow-2xl space-y-4 text-center">
              <div className="w-12 h-12 rounded-2xl bg-emerald-600/20 text-emerald-400 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-7 h-7" />
              </div>
              <div>
                <h3 className="text-lg font-black uppercase text-white">
                  {successReport.status === "PENDING_NETWORK"
                    ? "Saved Offline on Device"
                    : "Observation Submitted"}
                </h3>
                <div className="text-xs font-mono text-emerald-400 font-bold mt-1">
                  Reference: {successReport.report_number}
                </div>
              </div>

              <p className="text-xs text-slate-300 leading-relaxed max-w-xs mx-auto">
                {successReport.status === "PENDING_NETWORK"
                  ? "You are currently offline. Your report and photo are saved on your phone and will upload automatically as soon as internet is detected."
                  : "Thank you for reporting ground abnormalities. District engineers will review the photo and verify coordinates before notifying emergency teams."}
              </p>

              <button
                type="button"
                onClick={() => setSuccessReport(null)}
                className="w-full py-3 bg-slate-800 hover:bg-slate-700 text-white text-xs font-mono font-bold rounded-xl"
              >
                Submit Another Report
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmitReport} className="bg-slate-900 border border-slate-800 rounded-3xl p-5 space-y-4 shadow-xl">
              <div>
                <h2 className="text-sm font-black text-slate-100 uppercase tracking-wide flex items-center gap-2">
                  <Camera className="w-4 h-4 text-red-400" />
                  Report Slope Abnormality
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Notice ground cracks, rockfalls, or water mudflows? Submit a photo to alert district authorities.
                </p>
              </div>

              {/* 1. Category */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono uppercase font-bold text-slate-400">
                  1. Hazard Category
                </label>
                <div className="grid grid-cols-2 gap-1.5">
                  {CATEGORIES.map((cat) => (
                    <button
                      key={cat.id}
                      type="button"
                      onClick={() => setCategory(cat.id)}
                      className={`p-2.5 rounded-xl border text-left text-xs font-medium flex items-center gap-2 transition ${
                        category === cat.id
                          ? "bg-red-950/80 border-red-500 text-white font-bold"
                          : "bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700"
                      }`}
                    >
                      <span>{cat.icon}</span>
                      <span className="truncate">{cat.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* 2. Photo Upload with Client-Side Canvas Compression */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono uppercase font-bold text-slate-400 flex items-center justify-between">
                  <span>2. Photo Evidence (Camera or Gallery)</span>
                  {compressionInfo && (
                    <span className="text-emerald-400 text-[10px] font-mono lowercase">
                      {compressionInfo}
                    </span>
                  )}
                </label>

                {previewUrl ? (
                  <div className="relative rounded-2xl overflow-hidden border border-slate-700 bg-slate-950">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={previewUrl}
                      alt="Observation Preview"
                      className="w-full h-48 object-cover"
                    />
                    <button
                      type="button"
                      onClick={clearPhoto}
                      className="absolute top-2 right-2 w-7 h-7 rounded-full bg-black/70 text-white flex items-center justify-center hover:bg-black"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className="border-2 border-dashed border-slate-800 hover:border-slate-700 rounded-2xl p-4 text-center cursor-pointer bg-slate-950/50 flex flex-col items-center justify-center gap-2 transition"
                  >
                    <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center text-slate-300">
                      <Camera className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-slate-200">
                        Take Photo or Select from Device
                      </div>
                      <div className="text-[10px] text-slate-500 mt-0.5">
                        Compressed client-side before upload to work on 2G/3G mountain links
                      </div>
                    </div>
                  </div>
                )}

                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  capture="environment"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </div>

              {/* 3. Description */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono uppercase font-bold text-slate-400">
                  3. Description & Signs Observed
                </label>
                <textarea
                  rows={3}
                  required
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Longitudinal crack approximately 2 meters long on hillside cutting. Mud has started sliding into drainage ditch."
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-red-500"
                />
              </div>

              {/* 4. Location & Contact */}
              <div className="grid grid-cols-1 gap-3">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-mono uppercase font-bold text-slate-400">
                    Location Landmark
                  </label>
                  <input
                    type="text"
                    value={landmark}
                    onChange={(e) => setLandmark(e.target.value)}
                    placeholder="e.g. 200m before Haflong junction on hill bend"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-red-500"
                  />
                  <div className="text-[10px] font-mono text-slate-500 flex items-center gap-1">
                    <MapPin className="w-3 h-3 text-red-400" />
                    <span>{locStatus}</span>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[10px] font-mono uppercase font-bold text-slate-400">
                    Contact Phone (Optional)
                  </label>
                  <input
                    type="tel"
                    value={contactPhone}
                    onChange={(e) => setContactPhone(e.target.value)}
                    placeholder="+91..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-red-500 font-mono"
                  />
                </div>
              </div>

              {/* Verification Disclaimer */}
              <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-[11px] text-slate-400 flex items-start gap-2 leading-relaxed">
                <ShieldCheck className="w-4 h-4 text-indigo-400 flex-shrink-0 mt-0.5" />
                <span>
                  All citizen reports are human-reviewed by disaster management officers before regional alert dissemination.
                </span>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={submitting || isCompressing}
                className="w-full py-3.5 bg-red-600 hover:bg-red-500 text-white font-bold text-sm uppercase font-mono rounded-xl shadow-lg shadow-red-950/50 active:scale-[0.98] transition flex items-center justify-center gap-2"
              >
                {submitting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Transmitting Report...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    <span>SUBMIT HAZARD REPORT</span>
                  </>
                )}
              </button>
            </form>
          )}
        </>
      )}

      {/* TAB 2: RECENT REPORTS HISTORY */}
      {activeTab === "HISTORY" && (
        <div className="space-y-3">
          <div className="text-xs font-mono text-slate-400 flex items-center justify-between">
            <span>Verified Citizen Reports Stream</span>
            <button
              onClick={loadReportsHistory}
              className="text-red-400 hover:text-red-300 flex items-center gap-1 font-bold"
            >
              <RefreshCw className={`w-3 h-3 ${loadingHistory ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>

          {loadingHistory ? (
            <div className="py-12 text-center text-xs font-mono text-slate-500">
              Loading recent reports...
            </div>
          ) : reportsList.length > 0 ? (
            reportsList.map((rep) => {
              const isVerified = rep.status === "VERIFIED";
              const isReview = rep.status === "UNDER_REVIEW";

              return (
                <div
                  key={rep.id}
                  className="p-4 bg-slate-900 border border-slate-800 rounded-2xl space-y-2.5 shadow-md"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-mono font-bold text-slate-200">
                        {rep.report_number}
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        {rep.category.replace(/_/g, " ")}
                      </span>
                    </div>

                    <span
                      className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full uppercase border ${
                        isVerified
                          ? "bg-emerald-950 text-emerald-300 border-emerald-800"
                          : isReview
                          ? "bg-amber-950 text-amber-300 border-amber-800"
                          : "bg-slate-800 text-slate-400 border-slate-700"
                      }`}
                    >
                      {rep.status}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed font-medium">
                    {rep.description}
                  </p>

                  {rep.location_name && (
                    <div className="text-[11px] text-slate-400 flex items-center gap-1">
                      <MapPin className="w-3 h-3 text-red-400" />
                      <span>{rep.location_name}</span>
                    </div>
                  )}

                  {rep.photo_url && (
                    <div className="mt-2 rounded-xl overflow-hidden border border-slate-800">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={`${API_URL}${rep.photo_url}`}
                        alt="Hazard Evidence"
                        className="w-full h-36 object-cover"
                        onError={(e) => {
                          // Hide image if local upload link is inaccessible in dev
                          (e.target as HTMLElement).style.display = "none";
                        }}
                      />
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className="py-12 text-center text-xs font-mono text-slate-500">
              No recent hazard reports recorded in this sector.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
