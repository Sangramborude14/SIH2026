"use client";

import React, { useState, useEffect } from "react";
import {
  History,
  Play,
  Pause,
  RotateCcw,
  SkipForward,
  Activity,
  Sliders,
  Shield,
  Clock,
  ArrowLeft,
  ChevronRight,
  TrendingUp,
  BarChart2,
  Layers,
  CheckCircle2,
  AlertTriangle,
  Info,
  Award,
} from "lucide-react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface HistoricalIncident {
  id: string;
  name: string;
  location_id?: string;
  state: string;
  district: string;
  event_date: string;
  incident_type: string;
  actual_impact_summary: string;
  casualties: number;
  infrastructure_loss?: string;
  recorded_lead_time_hours: number;
  peak_rainfall_mm: number;
}

interface PlaybackFrame {
  step_offset_hours: number;
  timestamp_str: string;
  rainfall_1h_mm: number;
  rainfall_24h_mm: number;
  soil_moisture_pct: number;
  simulated_risk_score: number;
  simulated_risk_level: string;
  engine_state: string;
  ground_evidence?: string;
  early_warning_issued: boolean;
}

interface CalibrationMetrics {
  model_name?: string;
  dataset_name?: string;
  is_trained?: boolean;
  model_status?: string;
  precision?: number | null;
  recall?: number | null;
  f1_score?: number | null;
  roc_auc?: number | null;
  pr_auc?: number | null;
  brier_score?: number | null;
  confusion_matrix?: {
    true_positives: number;
    false_positives: number;
    false_negatives: number;
    true_negatives: number;
    total_evaluations: number;
  } | null;
  lead_time_distribution?: {
    mean_lead_time_hours: number;
    median_lead_time_hours: number;
    min_lead_time_hours: number;
    max_lead_time_hours: number;
    hist_bins: Record<string, number>;
  } | null;
  disclaimer?: string;
}


export default function AnalyticsAndCalibrationStudio() {
  const [incidents, setIncidents] = useState<HistoricalIncident[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>("");
  const [playbackFrames, setPlaybackFrames] = useState<PlaybackFrame[]>([]);
  const [currentFrameIdx, setCurrentFrameIdx] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [metrics, setMetrics] = useState<CalibrationMetrics | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Backtest State
  const [customWeights, setCustomWeights] = useState({
    rainfall_24h: 0.35,
    rainfall_72h: 0.15,
    soil_moisture: 0.20,
    slope_angle: 0.15,
    susceptibility: 0.15,
  });
  const [warningThreshold, setWarningThreshold] = useState<number>(70.0);
  const [backtestResult, setBacktestResult] = useState<any>(null);
  const [isBacktesting, setIsBacktesting] = useState<boolean>(false);

  useEffect(() => {
    async function loadInitialData() {
      try {
        setLoading(true);
        // 1. Load Incidents
        const incRes = await fetch(`${API_URL}/api/v1/analytics/incidents`);
        if (incRes.ok) {
          const incData: HistoricalIncident[] = await incRes.json();
          setIncidents(incData);
          if (incData.length > 0) {
            setSelectedIncidentId(incData[0].id);
          }
        }

        // 2. Load Calibration Metrics
        const metRes = await fetch(`${API_URL}/api/v1/analytics/metrics`);
        if (metRes.ok) {
          const metData: CalibrationMetrics = await metRes.json();
          setMetrics(metData);
        }
      } catch (err) {
        console.error("Failed to load analytics data", err);
      } finally {
        setLoading(false);
      }
    }
    loadInitialData();
  }, []);

  // Load Playback when selectedIncidentId changes
  useEffect(() => {
    if (!selectedIncidentId) return;
    async function loadPlayback() {
      try {
        const res = await fetch(`${API_URL}/api/v1/analytics/incidents/${selectedIncidentId}/playback`);
        if (res.ok) {
          const data = await res.json();
          setPlaybackFrames(data.playback_frames);
          setCurrentFrameIdx(0);
          setIsPlaying(false);
        }
      } catch (err) {
        console.error("Failed to load incident playback", err);
      }
    }
    loadPlayback();
  }, [selectedIncidentId]);

  // Playback Timer
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setCurrentFrameIdx((prev) => {
        if (prev >= playbackFrames.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, 1800);
    return () => clearInterval(interval);
  }, [isPlaying, playbackFrames.length]);

  const activeFrame = playbackFrames[currentFrameIdx] || null;
  const activeIncident = incidents.find((i) => i.id === selectedIncidentId) || null;

  const handleRunBacktest = async () => {
    try {
      setIsBacktesting(true);
      const res = await fetch(`${API_URL}/api/v1/analytics/backtest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          run_name: "Expert Custom Weights Simulation",
          weights: customWeights,
          warning_threshold_score: warningThreshold,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setBacktestResult(data);
      }
    } catch (err) {
      console.error("Backtest failed", err);
    } finally {
      setIsBacktesting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100 font-sans flex flex-col">
      {/* Header */}
      <header className="bg-slate-900 border-b border-slate-800 px-4 py-3 sm:px-6 sticky top-0 z-40 flex items-center justify-between shadow-md">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 flex items-center justify-center text-slate-300 transition"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase text-indigo-400 font-bold">
                DISASTRA • MODEL VALIDATION STUDIO
              </span>
              <span className="bg-amber-950/80 text-amber-300 border border-amber-800 text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase">
                DEMO / SIMULATED BENCHMARK
              </span>
              <span className="bg-slate-800 text-slate-300 border border-slate-700 text-[10px] font-mono px-2 py-0.5 rounded">
                Tier: Baseline Deterministic
              </span>
            </div>
            <h1 className="text-sm sm:text-base font-bold text-slate-100">
              Historical Disaster Playback &amp; Model Calibration Studio
            </h1>

          </div>
        </div>

        <div className="flex items-center gap-2 font-mono text-xs">
          <Link
            href="/"
            className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 transition"
          >
            Command HQ
          </Link>
        </div>
      </header>

      {/* Main Grid */}
      <main className="flex-1 p-4 sm:p-6 space-y-6 max-w-7xl mx-auto w-full">
        {/* Section 1: Forensic Timeline Playback Engine */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
                <History className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-slate-100">
                  Forensic Post-Disaster Timeline Reconstruction
                </h2>
                <p className="text-[11px] text-slate-400 font-mono">
                  Replays historical sensor feeds and measures early warning lead time.
                </p>
              </div>
            </div>

            {/* Benchmark Selector */}
            <div className="flex items-center gap-2 font-mono text-xs">
              <label className="text-slate-400 text-[11px]">Benchmark Incident:</label>
              <select
                value={selectedIncidentId}
                onChange={(e) => setSelectedIncidentId(e.target.value)}
                className="bg-slate-950 border border-slate-700 text-slate-200 px-3 py-1.5 rounded-lg text-xs font-mono focus:outline-none"
              >
                {incidents.map((inc) => (
                  <option key={inc.id} value={inc.id}>
                    {inc.name} ({inc.state})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Incident Overview Banner */}
          {activeIncident && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-slate-950 p-3.5 rounded-xl border border-slate-800 text-xs font-mono">
              <div>
                <span className="text-slate-500 text-[10px] uppercase block">Location:</span>
                <span className="text-slate-200 font-bold">{activeIncident.district}, {activeIncident.state}</span>
              </div>
              <div>
                <span className="text-slate-500 text-[10px] uppercase block">Event Date:</span>
                <span className="text-slate-200 font-bold">{new Date(activeIncident.event_date).toLocaleDateString()}</span>
              </div>
              <div>
                <span className="text-slate-500 text-[10px] uppercase block">Peak 24h Rainfall:</span>
                <span className="text-blue-400 font-bold">{activeIncident.peak_rainfall_mm} mm</span>
              </div>
              <div>
                <span className="text-slate-500 text-[10px] uppercase block">Engine Lead Time:</span>
                <span className="text-emerald-400 font-bold">{activeIncident.recorded_lead_time_hours}h Advance Alert</span>
              </div>
            </div>
          )}

          {/* Playback Telemetry & Trajectory Viewer */}
          {activeFrame && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-1">
              {/* Left: Telemetry Metrics Display (7 cols) */}
              <div className="lg:col-span-7 bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold font-mono text-indigo-400">
                    TIMELINE FRAME: {activeFrame.timestamp_str}
                  </span>
                  <span
                    className={`px-2.5 py-0.5 rounded text-[11px] font-mono font-bold uppercase ${
                      activeFrame.simulated_risk_level === "CRITICAL"
                        ? "bg-red-950 text-red-400 border border-red-800 animate-pulse"
                        : activeFrame.simulated_risk_level === "HIGH"
                        ? "bg-orange-950 text-orange-400 border border-orange-800"
                        : "bg-emerald-950 text-emerald-400 border border-emerald-800"
                    }`}
                  >
                    {activeFrame.engine_state} [{activeFrame.simulated_risk_score.toFixed(1)}/100]
                  </span>
                </div>

                {/* Animated Stat Gauges */}
                <div className="grid grid-cols-3 gap-3 font-mono text-center">
                  <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                    <div className="text-[10px] text-slate-400 uppercase">1h Rainfall</div>
                    <div className="text-sm font-black text-blue-400">{activeFrame.rainfall_1h_mm} mm</div>
                  </div>
                  <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                    <div className="text-[10px] text-slate-400 uppercase">24h Cumulative</div>
                    <div className="text-sm font-black text-blue-300">{activeFrame.rainfall_24h_mm} mm</div>
                  </div>
                  <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                    <div className="text-[10px] text-slate-400 uppercase">Soil Moisture</div>
                    <div className="text-sm font-black text-teal-400">{activeFrame.soil_moisture_pct}%</div>
                  </div>
                </div>

                {/* Ground Observation */}
                <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800 text-xs">
                  <span className="text-slate-400 font-mono text-[10px] uppercase block mb-1">
                    Telemetry &amp; Ground Evidence Log:
                  </span>
                  <p className="text-slate-200">{activeFrame.ground_evidence || "Normal background sensor monitoring."}</p>
                </div>

                {activeFrame.early_warning_issued && (
                  <div className="p-2.5 bg-emerald-950/60 border border-emerald-800 rounded-lg text-emerald-300 text-xs font-mono flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    <span>
                      EARLY WARNING DISPATCHED: Automated SMS/CAP alert broadcast triggered {activeIncident?.recorded_lead_time_hours}h prior to peak impact.
                    </span>
                  </div>
                )}
              </div>

              {/* Right: Scrub Timeline & Progress (5 cols) */}
              <div className="lg:col-span-5 bg-slate-950 p-4 rounded-xl border border-slate-800 flex flex-col justify-between space-y-4">
                <div>
                  <h3 className="text-xs font-bold font-mono text-slate-300 uppercase mb-2">
                    Timeline Playback Progress
                  </h3>
                  <div className="space-y-1.5 font-mono text-[11px]">
                    {playbackFrames.map((f, idx) => (
                      <button
                        key={idx}
                        onClick={() => setCurrentFrameIdx(idx)}
                        className={`w-full p-1.5 rounded text-left transition flex items-center justify-between ${
                          currentFrameIdx === idx
                            ? "bg-indigo-900/80 text-white font-bold border border-indigo-600"
                            : "hover:bg-slate-900 text-slate-400"
                        }`}
                      >
                        <span>{f.timestamp_str}</span>
                        <span className="text-[10px]">{f.simulated_risk_score.toFixed(0)}/100</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Play / Step Buttons */}
                <div className="flex items-center gap-2 pt-2 border-t border-slate-800">
                  <button
                    onClick={() => setIsPlaying(!isPlaying)}
                    className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white py-2 rounded-xl font-mono text-xs font-bold flex items-center justify-center gap-1.5 shadow-md"
                  >
                    {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                    <span>{isPlaying ? "Pause Playback" : "Play Timeline"}</span>
                  </button>

                  <button
                    onClick={() =>
                      setCurrentFrameIdx((prev) => (prev < playbackFrames.length - 1 ? prev + 1 : 0))
                    }
                    className="bg-slate-900 hover:bg-slate-800 text-slate-300 p-2 rounded-xl border border-slate-700"
                    title="Next Frame"
                  >
                    <SkipForward className="w-4 h-4" />
                  </button>

                  <button
                    onClick={() => setCurrentFrameIdx(0)}
                    className="bg-slate-900 hover:bg-slate-800 text-slate-300 p-2 rounded-xl border border-slate-700"
                    title="Reset to T-72h"
                  >
                    <RotateCcw className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Section 2: Model Statistical Calibration & Verification */}
        {metrics && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left: Metrics & Confusion Matrix (6 cols) */}
            <div className="lg:col-span-6 bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <Award className="w-5 h-5 text-amber-400" />
                  <div>
                    <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                      Statistical Verification &amp; Accuracy Metrics
                      <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-bold uppercase border ${
                        metrics.is_trained
                          ? "bg-emerald-950 text-emerald-300 border-emerald-800"
                          : "bg-amber-950 text-amber-400 border-amber-800"
                      }`}>
                        {metrics.is_trained ? "AUTHENTIC HELD-OUT VALIDATION" : "MODEL STATUS: NOT TRAINED"}
                      </span>
                    </h3>
                    <p className="text-[11px] text-slate-400 font-mono">
                      {metrics.is_trained
                        ? `Evaluation on held-out test split (${metrics.confusion_matrix?.total_evaluations ?? 0} samples).`
                        : "Awaiting training on curated GSI / NASA regional landslide catalogs."}
                    </p>
                  </div>
                </div>
              </div>

              {!metrics.is_trained ? (
                /* Clear NOT_TRAINED State Panel */
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
                  <div className="flex items-center gap-2 text-amber-400 font-mono font-bold text-xs">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                    <span>ML PREDICTION ENGINE: NOT TRAINED</span>
                  </div>
                  <p className="text-xs text-slate-300 font-sans leading-relaxed">
                    No trained machine-learning model artifact has been registered. Operational forecasts currently rely on the deterministic physical baseline engine.
                  </p>
                  <div className="text-[11px] font-mono text-slate-400 bg-slate-900/90 p-3 rounded-lg border border-slate-800 space-y-1.5">
                    <div className="font-bold text-slate-300">To train a genuine model on historical data:</div>
                    <ol className="list-decimal list-inside space-y-1 text-slate-400">
                      <li>Drop historical inventory in <code className="text-indigo-400">data/landslide_inventory/</code></li>
                      <li>Run CLI: <code className="text-emerald-400">python -m backend.app.ml.training.train --inventory ...</code></li>
                      <li>Held-out precision, recall, and ROC-AUC metrics will populate automatically.</li>
                    </ol>
                  </div>
                </div>
              ) : (
                <>
                  {/* Scientific Transparency Advisory Banner */}
                  <div className="bg-emerald-950/30 border border-emerald-800/50 rounded-xl p-3 flex items-start gap-2.5 text-xs text-emerald-200 font-mono">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                    <div className="space-y-0.5">
                      <div className="font-bold text-emerald-300">AUTHENTIC TEST EVALUATION</div>
                      <div className="text-[11px] text-slate-300 leading-relaxed font-sans">
                        Metrics below were computed on a held-out test split using leakage-safe temporal and spatial partitioning.
                      </div>
                    </div>
                  </div>

                  {/* Accuracy KPI Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono text-center">
                    <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800">
                      <div className="text-[10px] text-slate-400">PRECISION</div>
                      <div className="text-base font-black text-indigo-400">
                        {metrics.precision !== null && metrics.precision !== undefined
                          ? `${(metrics.precision * 100).toFixed(1)}%`
                          : "N/A"}
                      </div>
                    </div>

                    <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800">
                      <div className="text-[10px] text-slate-400">RECALL</div>
                      <div className="text-base font-black text-emerald-400">
                        {metrics.recall !== null && metrics.recall !== undefined
                          ? `${(metrics.recall * 100).toFixed(1)}%`
                          : "N/A"}
                      </div>
                    </div>

                    <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800">
                      <div className="text-[10px] text-slate-400">F1-SCORE</div>
                      <div className="text-base font-black text-purple-400">
                        {metrics.f1_score !== null && metrics.f1_score !== undefined
                          ? metrics.f1_score.toFixed(3)
                          : "N/A"}
                      </div>
                    </div>

                    <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800">
                      <div className="text-[10px] text-slate-400">ROC-AUC</div>
                      <div className="text-base font-black text-amber-400">
                        {metrics.roc_auc !== null && metrics.roc_auc !== undefined
                          ? metrics.roc_auc.toFixed(3)
                          : "N/A"}
                      </div>
                    </div>
                  </div>

                  {/* 2x2 Confusion Matrix */}
                  {metrics.confusion_matrix && (
                    <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 space-y-2">
                      <div className="text-xs font-mono font-bold text-slate-300 flex items-center justify-between">
                        <span>2×2 Confusion Matrix (N = {metrics.confusion_matrix.total_evaluations}):</span>
                        <span className="text-[10px] text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/60 font-bold uppercase">
                          HELD-OUT TEST SPLIT
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-2 font-mono text-center text-xs">
                        <div className="bg-emerald-950/60 p-3 rounded-lg border border-emerald-800">
                          <div className="text-[10px] text-emerald-400 font-bold uppercase">True Positives (TP)</div>
                          <div className="text-lg font-black text-emerald-300">{metrics.confusion_matrix.true_positives}</div>
                          <div className="text-[9px] text-slate-400">Correct Early Warnings</div>
                        </div>

                        <div className="bg-amber-950/60 p-3 rounded-lg border border-amber-800">
                          <div className="text-[10px] text-amber-400 font-bold uppercase">False Positives (FP)</div>
                          <div className="text-lg font-black text-amber-300">{metrics.confusion_matrix.false_positives}</div>
                          <div className="text-[9px] text-slate-400">False Alarms</div>
                        </div>

                        <div className="bg-red-950/60 p-3 rounded-lg border border-red-800">
                          <div className="text-[10px] text-red-400 font-bold uppercase">False Negatives (FN)</div>
                          <div className="text-lg font-black text-red-300">{metrics.confusion_matrix.false_negatives}</div>
                          <div className="text-[9px] text-slate-400">Missed Events</div>
                        </div>

                        <div className="bg-slate-900 p-3 rounded-lg border border-slate-700">
                          <div className="text-[10px] text-slate-300 font-bold uppercase">True Negatives (TN)</div>
                          <div className="text-lg font-black text-slate-200">{metrics.confusion_matrix.true_negatives}</div>
                          <div className="text-[9px] text-slate-400">Correct Stable Baseline</div>
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>


            {/* Right: Factor Weight Tuning Sandbox (6 cols) */}
            <div className="lg:col-span-6 bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
              <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                <Sliders className="w-5 h-5 text-indigo-400" />
                <div>
                  <h3 className="text-sm font-bold text-slate-100">
                    Model Factor Weight Tuning &amp; Backtesting Sandbox
                  </h3>
                  <p className="text-[11px] text-slate-400 font-mono">
                    Adjust scientific weights and simulate impact on historical precision &amp; lead time.
                  </p>
                </div>
              </div>

              {/* Sliders */}
              <div className="space-y-3 text-xs font-mono">
                <div>
                  <div className="flex justify-between text-[11px] text-slate-300 mb-1">
                    <span>24h Rainfall Weight:</span>
                    <strong className="text-indigo-400">{customWeights.rainfall_24h.toFixed(2)}</strong>
                  </div>
                  <input
                    type="range"
                    min="0.1"
                    max="0.6"
                    step="0.05"
                    value={customWeights.rainfall_24h}
                    onChange={(e) =>
                      setCustomWeights({ ...customWeights, rainfall_24h: parseFloat(e.target.value) })
                    }
                    className="w-full accent-indigo-500"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-[11px] text-slate-300 mb-1">
                    <span>Soil Moisture Saturation Weight:</span>
                    <strong className="text-teal-400">{customWeights.soil_moisture.toFixed(2)}</strong>
                  </div>
                  <input
                    type="range"
                    min="0.1"
                    max="0.4"
                    step="0.05"
                    value={customWeights.soil_moisture}
                    onChange={(e) =>
                      setCustomWeights({ ...customWeights, soil_moisture: parseFloat(e.target.value) })
                    }
                    className="w-full accent-teal-500"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-[11px] text-slate-300 mb-1">
                    <span>Warning Trigger Threshold:</span>
                    <strong className="text-amber-400">{warningThreshold} / 100</strong>
                  </div>
                  <input
                    type="range"
                    min="50"
                    max="85"
                    step="5"
                    value={warningThreshold}
                    onChange={(e) => setWarningThreshold(parseFloat(e.target.value))}
                    className="w-full accent-amber-500"
                  />
                </div>

                <button
                  onClick={handleRunBacktest}
                  disabled={isBacktesting}
                  className="w-full bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:opacity-50 text-white py-2.5 rounded-xl font-bold font-mono transition shadow-lg shadow-indigo-950 flex items-center justify-center gap-2"
                >
                  <Activity className="w-4 h-4" />
                  {isBacktesting ? "Running Backtesting Simulation..." : "RUN BACKTESTING SIMULATION"}
                </button>
              </div>

              {/* Backtest Result Output */}
              {backtestResult && (
                <div className="bg-slate-950 p-3 rounded-xl border border-indigo-900/60 space-y-2 text-xs font-mono">
                  <div className="flex justify-between items-center text-indigo-300 font-bold">
                    <span>Backtest Result ({backtestResult.run_name}):</span>
                    <span>F1: {backtestResult.f1_score.toFixed(3)}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-300">
                    <div>Mean Lead Time: <strong>{backtestResult.mean_lead_time_hours}h</strong></div>
                    <div>ROC-AUC: <strong>{backtestResult.roc_auc.toFixed(3)}</strong></div>
                  </div>
                  <p className="text-slate-400 text-[10px] pt-1 border-t border-slate-800">
                    {backtestResult.recommendation}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
