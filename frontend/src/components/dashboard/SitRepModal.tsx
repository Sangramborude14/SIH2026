"use client";

import React, { useState, useEffect } from "react";
import {
  FileText,
  Printer,
  Copy,
  CheckCircle2,
  AlertTriangle,
  Building2,
  Shield,
  Activity,
  Users,
  Compass,
  Clock,
  X,
} from "lucide-react";

interface SitRepDetail {
  report_number: string;
  incident_name: string;
  location_name: string;
  state: string;
  reporting_officer: string;
  generated_at: string;
  operational_period: string;
  executive_summary: string;
  sections: {
    heading: string;
    content: string;
    key_metrics?: Record<string, any> | null;
  }[];
  data_mode: string;
}

interface SitRepModalProps {
  eventId: string;
  apiUrl: string;
  onClose: () => void;
}

export default function SitRepModal({ eventId, apiUrl, onClose }: SitRepModalProps) {
  const [sitrep, setSitrep] = useState<SitRepDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    async function loadSitRep() {
      try {
        setLoading(true);
        const res = await fetch(`${apiUrl}/api/v1/alerts/sitrep/${eventId}`);
        if (res.ok) {
          const data: SitRepDetail = await res.json();
          setSitrep(data);
        }
      } catch (err) {
        console.error("Failed to load SitRep", err);
      } finally {
        setLoading(false);
      }
    }
    if (eventId) {
      loadSitRep();
    }
  }, [eventId, apiUrl]);

  const handleCopy = () => {
    if (!sitrep) return;
    const text = `SITUATION REPORT (NDMA / SDRF)
Report Number: ${sitrep.report_number}
Incident: ${sitrep.incident_name}
Sector: ${sitrep.location_name}, ${sitrep.state}
Operational Period: ${sitrep.operational_period}

EXECUTIVE SUMMARY:
${sitrep.executive_summary}

${sitrep.sections.map((s) => `--- ${s.heading.toUpperCase()} ---\n${s.content}`).join("\n\n")}

Generated: ${sitrep.generated_at}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="fixed inset-0 bg-black/85 z-50 flex items-center justify-center p-3 sm:p-5">
      <div className="bg-zinc-950 border border-zinc-800 rounded w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh] font-sans text-white">
        {/* Modal Top Action Bar */}
        <div className="bg-black px-5 py-3 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-zinc-400" />
            <h2 className="text-sm font-black text-white font-mono uppercase tracking-wider">
              National Disaster Management Authority (NDMA) SitRep
            </h2>
          </div>

          <div className="flex items-center gap-2 font-mono text-xs">
            <button
              onClick={handleCopy}
              className="px-3 py-1 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-white rounded transition flex items-center gap-1.5 font-bold"
            >
              {copied ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? "Copied" : "Copy"}
            </button>

            <button
              onClick={handlePrint}
              className="px-3 py-1 bg-white hover:bg-zinc-200 text-black rounded transition flex items-center gap-1.5 font-black shadow-sm"
            >
              <Printer className="w-3.5 h-3.5" />
              Print
            </button>

            <button
              onClick={onClose}
              className="text-zinc-400 hover:text-white p-1 rounded hover:bg-zinc-900 transition ml-2"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* SitRep Document Content */}
        <div className="p-5 sm:p-6 space-y-4 overflow-y-auto flex-1 text-xs font-sans bg-black">
          {loading ? (
            <div className="py-16 text-center text-zinc-500 font-mono">
              Compiling formal tactical Situation Report...
            </div>
          ) : sitrep ? (
            <div className="bg-zinc-950 border border-zinc-800 rounded p-5 space-y-4 shadow-lg">
              {/* Document Meta Header */}
              <div className="border-b border-zinc-800 pb-3 space-y-1 font-mono text-[11px]">
                <div className="flex justify-between items-center text-zinc-400 font-bold">
                  <span>DISASTER MANAGEMENT ADVISORY BRIEFING</span>
                  <span>{sitrep.data_mode} MODE</span>
                </div>
                <h1 className="text-base font-black text-white font-sans">{sitrep.incident_name}</h1>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-zinc-400 pt-1 text-[10px]">
                  <div>Report No: <strong className="text-white">{sitrep.report_number}</strong></div>
                  <div>Period: <strong className="text-white">{sitrep.operational_period}</strong></div>
                  <div>Officer: <strong className="text-white">{sitrep.reporting_officer}</strong></div>
                </div>
              </div>

              {/* Executive Summary */}
              <div className="space-y-1.5 bg-black p-3.5 rounded border border-zinc-800">
                <h3 className="text-xs font-black font-mono text-orange-300 uppercase">
                  Executive Summary
                </h3>
                <p className="text-zinc-200 leading-relaxed text-xs">{sitrep.executive_summary}</p>
              </div>

              {/* Formatted Sections */}
              <div className="space-y-4 pt-2">
                {sitrep.sections.map((sec, idx) => (
                  <div key={idx} className="space-y-2 border-b border-zinc-850 pb-3 last:border-b-0">
                    <h4 className="text-xs font-black font-mono text-white flex items-center gap-1.5 uppercase">
                      <span className="w-1.5 h-1.5 rounded-full bg-white" />
                      {sec.heading}
                    </h4>
                    <p className="text-zinc-300 leading-relaxed whitespace-pre-line pl-3 text-[11px]">
                      {sec.content}
                    </p>

                    {sec.key_metrics && (
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 pl-3 pt-1 font-mono text-[10px]">
                        {Object.entries(sec.key_metrics).map(([k, v]) => (
                          <div key={k} className="bg-black p-1.5 rounded border border-zinc-800 flex justify-between">
                            <span className="text-zinc-400 capitalize">{k.replace(/_/g, " ")}:</span>
                            <span className="text-white font-bold ml-1">{String(v)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Document Signoff */}
              <div className="pt-3 border-t border-zinc-800 flex items-center justify-between text-[10px] font-mono text-zinc-500">
                <span>Generated by DISASTRA Multi-Signal Intelligence Pipeline</span>
                <span>Verified by {sitrep.reporting_officer}</span>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
