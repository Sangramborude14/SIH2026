"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import CommandHeader from "@/components/dashboard/CommandHeader";
import SitRepModal from "@/components/dashboard/SitRepModal";
import { DisasterEventItem, EventTimelineMilestoneItem, RiskAssessmentItem } from "@/components/dashboard/types";
import { formatFactorTelemetry } from "@/lib/formatters";
import {
  AlertTriangle,
  AlertOctagon,
  CheckCircle2,
  ShieldAlert,
  Clock,
  Send,
  FileText,
  MapPin,
  ArrowUpRight,
  Filter,
  Check,
  Search,
  ChevronRight,
  Layers,
  Activity,
  Loader2,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function EventsQueueContent() {
  const searchParams = useSearchParams();
  const initialEventId = searchParams.get("id");

  const [events, setEvents] = useState<DisasterEventItem[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(initialEventId);
  const [timeline, setTimeline] = useState<EventTimelineMilestoneItem[]>([]);
  const [latestAssessment, setLatestAssessment] = useState<RiskAssessmentItem | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isAcknowledging, setIsAcknowledging] = useState<boolean>(false);
  const [sitrepEventId, setSitrepEventId] = useState<string | null>(null);

  // Fetch events
  const fetchEvents = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/events`);
      if (res.ok) {
        const evs: DisasterEventItem[] = await res.json();
        setEvents(evs);
        if (!selectedEventId && evs.length > 0) {
          setSelectedEventId(evs[0].id);
        }
      }
    } catch (err) {
      console.error("Failed to fetch events", err);
    } finally {
      setLoading(false);
    }
  }, [selectedEventId]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // Fetch timeline and assessment for selected event
  useEffect(() => {
    if (!selectedEventId) return;
    const fetchEventDetails = async () => {
      try {
        const tlRes = await fetch(`${API_URL}/api/v1/events/${selectedEventId}/timeline`);
        if (tlRes.ok) {
          const tlData = await tlRes.json();
          setTimeline(tlData);
        }
        const activeEv = events.find((e) => e.id === selectedEventId);
        if (activeEv) {
          const invRes = await fetch(`${API_URL}/api/v1/locations/${activeEv.location_id}/investigate`);
          if (invRes.ok) {
            const invData = await invRes.json();
            setLatestAssessment(invData.latest_assessment);
          }
        }
      } catch (err) {
        console.error("Failed to load event timeline", err);
      }
    };
    fetchEventDetails();
  }, [selectedEventId, events]);

  // Acknowledge selected event
  const handleAcknowledge = async (evId: string) => {
    setIsAcknowledging(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/events/${evId}/acknowledge`, { method: "POST" });
      if (res.ok) {
        await fetchEvents();
      }
    } catch (err) {
      console.error("Failed to acknowledge event", err);
    } finally {
      setIsAcknowledging(false);
    }
  };

  const filteredEvents = events.filter((ev) => {
    if (statusFilter !== "ALL" && ev.status !== statusFilter) return false;
    if (severityFilter !== "ALL" && ev.severity !== severityFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchType = ev.event_type?.toLowerCase().includes(q);
      const matchSum = ev.summary?.toLowerCase().includes(q);
      const matchLoc = ev.location_id?.toLowerCase().includes(q);
      if (!matchType && !matchSum && !matchLoc) return false;
    }
    return true;
  });

  const selectedEvent = events.find((e) => e.id === selectedEventId) || filteredEvents[0] || null;
  const factors = latestAssessment?.factors || [];

  return (
    <div className="min-h-screen bg-black text-white flex flex-col font-sans">
      <CommandHeader
        engineOnline={true}
        engineStatusText="ONLINE"
        lastUpdated="LIVE"
        dataMode="LIVE"
        onToggleDataMode={async () => {}}
      />

      <main className="flex-1 p-3.5 sm:p-5 max-w-[1700px] w-full mx-auto space-y-4 font-mono text-xs">
        {/* Top Filter Bar */}
        <div className="bg-zinc-950 border border-zinc-800 rounded p-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] text-zinc-400 font-bold uppercase flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5 text-zinc-400" />
              Status:
            </span>
            {["ALL", "ACTIVE", "ESCALATED", "RESOLVED"].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-2.5 py-1 rounded text-[10px] font-bold transition uppercase ${
                  statusFilter === st ? "bg-white text-black font-black" : "bg-zinc-900 text-zinc-400 hover:text-white"
                }`}
              >
                {st}
              </button>
            ))}

            <span className="text-zinc-700 mx-1">|</span>

            <span className="text-[11px] text-zinc-400 font-bold uppercase">Severity:</span>
            {["ALL", "CRITICAL", "HIGH", "MODERATE"].map((sev) => (
              <button
                key={sev}
                onClick={() => setSeverityFilter(sev)}
                className={`px-2.5 py-1 rounded text-[10px] font-bold transition uppercase ${
                  severityFilter === sev ? "bg-white text-black font-black" : "bg-zinc-900 text-zinc-400 hover:text-white"
                }`}
              >
                {sev}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search events or stations..."
                className="bg-black border border-zinc-800 rounded pl-8 pr-3 py-1 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600 font-mono w-48 sm:w-64"
              />
            </div>
            <span className="text-zinc-500 text-[10px] whitespace-nowrap">
              {filteredEvents.length} of {events.length} Incidents
            </span>
          </div>
        </div>

        {/* Main Grid: Events List (Left 5 cols) + Selected Event Detail (Right 7 cols) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
          {/* Left Column: Events Queue */}
          <div className="lg:col-span-5 space-y-2">
            {filteredEvents.length > 0 ? (
              <div className="space-y-2 max-h-[750px] overflow-y-auto pr-1">
                {filteredEvents.map((ev) => {
                  const isSelected = ev.id === selectedEvent?.id;
                  const isCrit = ev.severity === "CRITICAL";
                  return (
                    <div
                      key={ev.id}
                      onClick={() => setSelectedEventId(ev.id)}
                      className={`p-3 rounded border transition cursor-pointer ${
                        isSelected
                          ? "bg-zinc-900 border-white shadow-sm"
                          : isCrit
                          ? "bg-red-950/20 border-red-900/50 hover:bg-red-950/40"
                          : "bg-zinc-950 border-zinc-800 hover:bg-zinc-900/60"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-[9px] font-black px-1.5 py-0.5 rounded uppercase border ${
                              isCrit
                                ? "bg-red-950 text-red-300 border-red-700"
                                : ev.severity === "HIGH"
                                ? "bg-orange-950 text-orange-300 border-orange-700"
                                : "bg-amber-950 text-amber-300 border-amber-700"
                            }`}
                          >
                            {ev.severity}
                          </span>
                          <span className="text-zinc-400 font-bold text-[10px]">{ev.location_id}</span>
                        </div>
                        <span className="text-zinc-500 text-[10px]">{ev.status}</span>
                      </div>

                      <h4 className="text-white font-bold text-xs leading-snug mb-1">
                        {ev.summary || ev.event_type?.replace(/_/g, " ")}
                      </h4>

                      <div className="flex items-center justify-between text-[10px] text-zinc-400 pt-1 border-t border-zinc-850/60">
                        <span>Risk Score: <strong className="text-white">{ev.risk_score.toFixed(1)}</strong></span>
                        <span>Updated: {new Date(ev.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="p-8 bg-zinc-950 border border-zinc-850 rounded text-center text-zinc-500">
                No incidents match the active filters.
              </div>
            )}
          </div>

          {/* Right Column: Event Detail & Attribution */}
          <div className="lg:col-span-7 space-y-4">
            {selectedEvent ? (
              <div className="bg-zinc-950 border border-zinc-800 rounded p-4 space-y-4">
                {/* Event Header & Action Buttons */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-850 pb-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] bg-red-950 text-red-300 border border-red-700 px-2 py-0.5 rounded font-black uppercase">
                        {selectedEvent.severity}
                      </span>
                      <span className="text-zinc-400 text-xs font-bold">{selectedEvent.location_id}</span>
                      <span className="text-zinc-600">&bull;</span>
                      <span className="text-zinc-400 text-[11px]">{selectedEvent.status}</span>
                    </div>
                    <h2 className="text-base font-black text-white">{selectedEvent.summary || selectedEvent.event_type?.replace(/_/g, " ")}</h2>
                  </div>

                  {/* Actions Strip */}
                  <div className="flex items-center gap-2 flex-wrap">
                    {selectedEvent.status !== "ACKNOWLEDGED" && selectedEvent.status !== "RESOLVED" && (
                      <button
                        onClick={() => handleAcknowledge(selectedEvent.id)}
                        disabled={isAcknowledging}
                        className="bg-white hover:bg-zinc-200 text-black px-3 py-1.5 rounded font-black text-xs transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>{isAcknowledging ? "Saving..." : "Acknowledge"}</span>
                      </button>
                    )}

                    <button
                      onClick={() => setSitrepEventId(selectedEvent.id)}
                      className="bg-zinc-900 hover:bg-zinc-800 text-white border border-zinc-700 px-3 py-1.5 rounded font-bold text-xs transition flex items-center gap-1.5 cursor-pointer"
                    >
                      <FileText className="w-3.5 h-3.5" />
                      <span>Generate SitRep</span>
                    </button>

                    <Link
                      href={`/broadcast?eventId=${selectedEvent.id}&locationId=${selectedEvent.location_id}`}
                      className="bg-red-600 hover:bg-red-500 text-white px-3 py-1.5 rounded font-black text-xs transition flex items-center gap-1.5"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>Broadcast Warning</span>
                    </Link>

                    <Link
                      href={`/stations?id=${selectedEvent.location_id}`}
                      className="text-emerald-400 hover:text-emerald-300 px-2 py-1.5 font-bold text-xs flex items-center gap-1 transition"
                    >
                      <span>Station 360</span>
                      <ArrowUpRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                </div>

                {/* Analytical Narrative */}
                <div className="bg-black border border-zinc-850 p-3 rounded space-y-1">
                  <div className="text-[10px] text-zinc-400 uppercase font-bold">Scientific Hazard Synthesis</div>
                  <p className="text-zinc-300 font-sans text-xs leading-relaxed">
                    {selectedEvent.summary ||
                      "Continuous extreme precipitation combined with saturated soil profile has elevated geotechnical shear stress beyond regional failure threshold."}
                  </p>
                </div>

                {/* Normalized Factor Breakdown (Zero [object Object]) */}
                <div className="space-y-2">
                  <div className="text-[11px] text-zinc-300 font-bold uppercase flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-zinc-400" />
                    Normalized Factor Attribution (0.0 to 1.0)
                  </div>
                  {factors.length > 0 ? (
                    <div className="overflow-x-auto rounded border border-zinc-800 bg-black">
                      <table className="w-full text-left text-xs font-mono">
                        <thead className="bg-zinc-900 text-zinc-400 border-b border-zinc-800 text-[10px] uppercase font-bold">
                          <tr>
                            <th className="px-3 py-2">Indicator</th>
                            <th className="px-3 py-2">Measured Telemetry</th>
                            <th className="px-3 py-2">Score</th>
                            <th className="px-3 py-2">Contribution</th>
                            <th className="px-3 py-2">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-850">
                          {factors.map((f) => (
                            <tr key={f.name} className="hover:bg-zinc-900/40">
                              <td className="px-3 py-2 text-zinc-200 font-bold capitalize">{f.name.replace(/_/g, " ")}</td>
                              <td className="px-3 py-2 text-zinc-400">{formatFactorTelemetry(f.raw_value, f.name)}</td>
                              <td className="px-3 py-2 text-zinc-300 font-bold">{(f.normalized_score ?? 0).toFixed(2)}</td>
                              <td className="px-3 py-2 text-white font-black">+{f.contribution.toFixed(1)} pts</td>
                              <td className="px-3 py-2">
                                <span
                                  className={`text-[9px] px-1.5 py-0.5 rounded font-black uppercase border ${
                                    f.status === "CRITICAL"
                                      ? "bg-red-950 text-red-300 border-red-700"
                                      : f.status === "HIGH"
                                      ? "bg-orange-950 text-orange-300 border-orange-700"
                                      : "bg-amber-950 text-amber-300 border-amber-700"
                                  }`}
                                >
                                  {f.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-zinc-500 italic p-3 bg-black rounded border border-zinc-850">
                      Factor breakdown loading from station telemetry...
                    </div>
                  )}
                </div>

                {/* Timeline Milestones */}
                <div className="space-y-2">
                  <div className="text-[11px] text-zinc-300 font-bold uppercase flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-zinc-400" />
                    Incident Progression Milestones
                  </div>
                  {timeline.length > 0 ? (
                    <div className="space-y-1.5">
                      {timeline.slice(-4).map((m, idx) => (
                        <div key={idx} className="p-2.5 bg-black border border-zinc-850 rounded flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                            <div>
                              <strong className="text-white text-xs">{m.title}</strong>
                              <p className="text-[11px] text-zinc-400 font-sans">{m.description}</p>
                            </div>
                          </div>
                          <span className="text-[10px] text-zinc-500">{m.time_label}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-zinc-500 italic p-3 bg-black rounded border border-zinc-850">
                      Telemetry tracking initial threshold exceedance...
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-12 bg-zinc-950 border border-zinc-850 rounded text-center text-zinc-500">
                Select an incident from the queue to inspect scientific telemetry and trigger response directives.
              </div>
            )}
          </div>
        </div>
      </main>

      {/* SitRep Modal */}
      {sitrepEventId && (
        <SitRepModal
          eventId={sitrepEventId}
          apiUrl={API_URL}
          onClose={() => setSitrepEventId(null)}
        />
      )}
    </div>
  );
}

export default function EventsQueuePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-black text-white flex items-center justify-center font-mono text-xs">
          <Loader2 className="w-6 h-6 animate-spin text-white mr-2" />
          <span>Loading Events Queue...</span>
        </div>
      }
    >
      <EventsQueueContent />
    </Suspense>
  );
}
