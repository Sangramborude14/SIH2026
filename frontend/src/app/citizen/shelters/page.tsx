"use client";

import React, { useState, useEffect } from "react";
import {
  MapPin,
  Phone,
  Shield,
  Building,
  Users,
  Compass,
  CheckCircle2,
  ExternalLink,
  ChevronRight,
  Info,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ShelterItem {
  id: string;
  name: string;
  location_id: string;
  latitude: number;
  longitude: number;
  point_type: string;
  capacity?: number | null;
  availability: string;
  source: string;
  contact_number?: string | null;
  distance_km?: number | null;
}

interface ContactsData {
  national_emergency: string;
  disaster_management_helpline: string;
  district_disaster_helpline: string;
  ambulance_service: string;
  police_helpline: string;
  fire_rescue: string;
  ner_state_control_rooms: Record<string, string>;
}

export default function CitizenSheltersPage() {
  const [shelters, setShelters] = useState<ShelterItem[]>([]);
  const [contacts, setContacts] = useState<ContactsData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        // Load Shelters
        const sRes = await fetch(`${API_URL}/api/v1/citizen/shelters`);
        if (sRes.ok) {
          const sData: ShelterItem[] = await sRes.json();
          setShelters(sData);
        }

        // Load Contacts
        const cRes = await fetch(`${API_URL}/api/v1/citizen/contacts`);
        if (cRes.ok) {
          const cData: ContactsData = await cRes.json();
          setContacts(cData);
        }
      } catch (err) {
        console.warn("Could not load shelters/contacts", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-5 shadow-xl">
        <div className="flex items-center gap-2 text-emerald-400 mb-1">
          <Building className="w-5 h-5" />
          <span className="text-[10px] font-mono uppercase font-black tracking-wider">
            COMMUNITY AID & ASSEMBLY
          </span>
        </div>
        <h1 className="text-lg font-black text-slate-100 uppercase tracking-tight">
          Designated Shelters & Helplines
        </h1>
        <p className="text-xs text-slate-400 mt-1 leading-relaxed">
          Pre-identified safe assembly grounds, medical aid posts, and verified disaster control room hotlines across North Eastern India.
        </p>
      </div>

      {/* 1. Core National Emergency Hotlines (Fast Tap Dialers) */}
      <section className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
        <div className="text-xs font-bold font-mono uppercase text-slate-200 flex items-center gap-1.5">
          <Phone className="w-4 h-4 text-red-400" />
          Priority Emergency Dialers
        </div>

        <div className="grid grid-cols-2 gap-2">
          <a
            href="tel:112"
            className="p-3 bg-red-950/40 hover:bg-red-900/50 border border-red-800/80 rounded-xl flex items-center justify-between transition"
          >
            <div>
              <div className="text-[10px] font-mono uppercase text-red-300 font-bold">National All-In-One</div>
              <div className="text-xs text-slate-300">All Emergencies</div>
            </div>
            <div className="text-base font-black text-red-400 font-mono">112</div>
          </a>

          <a
            href="tel:1070"
            className="p-3 bg-indigo-950/40 hover:bg-indigo-900/50 border border-indigo-800/80 rounded-xl flex items-center justify-between transition"
          >
            <div>
              <div className="text-[10px] font-mono uppercase text-indigo-300 font-bold">SDMA Disaster</div>
              <div className="text-xs text-slate-300">State Control</div>
            </div>
            <div className="text-base font-black text-indigo-400 font-mono">1070</div>
          </a>

          <a
            href="tel:1077"
            className="p-3 bg-slate-950 hover:bg-slate-800 border border-slate-800 rounded-xl flex items-center justify-between transition"
          >
            <div>
              <div className="text-[10px] font-mono uppercase text-slate-400 font-bold">DDMA District</div>
              <div className="text-xs text-slate-300">District Control</div>
            </div>
            <div className="text-base font-black text-slate-200 font-mono">1077</div>
          </a>

          <a
            href="tel:108"
            className="p-3 bg-slate-950 hover:bg-slate-800 border border-slate-800 rounded-xl flex items-center justify-between transition"
          >
            <div>
              <div className="text-[10px] font-mono uppercase text-emerald-400 font-bold">Ambulance</div>
              <div className="text-xs text-slate-300">Medical Aid</div>
            </div>
            <div className="text-base font-black text-emerald-400 font-mono">108</div>
          </a>
        </div>
      </section>

      {/* 2. Verified Safer Reference Points & Shelters */}
      <section className="space-y-2.5">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold font-mono uppercase text-slate-300 flex items-center gap-1.5">
            <MapPin className="w-4 h-4 text-emerald-400" />
            Verified Safe Assembly Grounds & Shelters
          </h2>
          <span className="text-[10px] font-mono text-slate-500">
            {shelters.length} Facilities
          </span>
        </div>

        {loading ? (
          <div className="py-10 text-center text-xs font-mono text-slate-500">
            Loading verified shelters...
          </div>
        ) : shelters.length > 0 ? (
          shelters.map((shelter) => {
            const isOpen = shelter.availability === "OPEN";

            return (
              <div
                key={shelter.id}
                className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-2 shadow-sm"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-xs font-bold text-slate-100">{shelter.name}</h3>
                    <div className="text-[10px] font-mono text-slate-400 mt-0.5 flex items-center gap-2">
                      <span>Type: {shelter.point_type.replace(/_/g, " ")}</span>
                      {shelter.capacity && <span>• Cap: ~{shelter.capacity} people</span>}
                    </div>
                  </div>

                  <span
                    className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full uppercase border ${
                      isOpen
                        ? "bg-emerald-950 text-emerald-300 border-emerald-800"
                        : "bg-red-950 text-red-300 border-red-800"
                    }`}
                  >
                    {shelter.availability}
                  </span>
                </div>

                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-[10px] text-slate-500 font-mono">
                    Source: {shelter.source}
                  </span>

                  {shelter.contact_number && (
                    <a
                      href={`tel:${shelter.contact_number.split("/")[0].trim()}`}
                      className="text-xs font-mono text-emerald-400 hover:underline flex items-center gap-1 font-bold"
                    >
                      <Phone className="w-3 h-3" />
                      {shelter.contact_number.split("/")[0].trim()}
                    </a>
                  )}
                </div>
              </div>
            );
          })
        ) : (
          <div className="py-8 text-center text-xs font-mono text-slate-500">
            No shelters configured for current query.
          </div>
        )}
      </section>

      {/* 3. North Eastern Region State Control Rooms */}
      {contacts?.ner_state_control_rooms && (
        <section className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
          <div className="text-xs font-bold font-mono uppercase text-slate-200 flex items-center gap-1.5">
            <Shield className="w-4 h-4 text-indigo-400" />
            North Eastern States Disaster Control Rooms
          </div>

          <div className="space-y-1.5">
            {Object.entries(contacts.ner_state_control_rooms).map(([stateName, phoneNum]) => {
              const primaryPhone = phoneNum.split("/")[0].trim();
              return (
                <div
                  key={stateName}
                  className="bg-slate-950 p-2.5 rounded-xl border border-slate-800 flex items-center justify-between text-xs"
                >
                  <span className="text-slate-300 font-medium">{stateName}</span>
                  <a
                    href={`tel:${primaryPhone.replace(/\s+/g, "")}`}
                    className="font-mono text-indigo-400 hover:underline font-bold flex items-center gap-1"
                  >
                    <Phone className="w-3 h-3" />
                    {primaryPhone}
                  </a>
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
