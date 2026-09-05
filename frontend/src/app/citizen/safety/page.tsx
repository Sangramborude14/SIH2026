"use client";

import React, { useState, useEffect } from "react";
import {
  Shield,
  CheckCircle2,
  AlertTriangle,
  BookOpen,
  Eye,
  Backpack,
  Phone,
  ArrowRight,
  Info,
  ChevronRight,
} from "lucide-react";
import Link from "next/link";

interface ImmediateGuidanceItem {
  category: string;
  instruction: string;
}

interface GuidanceSection {
  phase: string; // BEFORE, DURING, AFTER
  title: string;
  instructions: ImmediateGuidanceItem[];
}

export default function CitizenSafetyGuidePage() {
  const [activeTab, setActiveTab] = useState<"BEFORE" | "DURING" | "AFTER">("BEFORE");
  const [checkedKitItems, setCheckedKitItems] = useState<Record<string, boolean>>({});

  // Interactive Checklist persistence
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("disastra_citizen_gobag");
        if (saved) setCheckedKitItems(JSON.parse(saved));
      } catch (e) {
        console.warn("Could not load go-bag checklist", e);
      }
    }
  }, []);

  const toggleKitItem = (item: string) => {
    const updated = { ...checkedKitItems, [item]: !checkedKitItems[item] };
    setCheckedKitItems(updated);
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("disastra_citizen_gobag", JSON.stringify(updated));
      } catch (e) {
        console.warn("Could not save go-bag checklist", e);
      }
    }
  };

  const sections: Record<string, { title: string; subtitle: string; dos: string[]; donts: string[] }> = {
    BEFORE: {
      title: "Before a Landslide",
      subtitle: "Preparedness, Home Inspection & Early Awareness",
      dos: [
        "Familiarize yourself with local landslide history and identify higher, stable ridge zones.",
        "Inspect and clean drainage channels (jhoras) and roof runoff gutters to prevent soil water saturation.",
        "Prepare an emergency Go-Bag with torch, fresh water, dry food, and essential medications.",
        "Discuss an evacuation rendezvous point with all family members in case phones fail.",
        "Sign up for localized district disaster alerts and weather warnings.",
      ],
      donts: [
        "Do NOT construct unpermitted retaining walls or cut into steep slopes without engineering advice.",
        "Do NOT dump excavated road dirt, debris, or domestic waste directly into drainage gullies.",
        "Do NOT ignore small ground fissures, tilted fence posts, or jamming doors/windows.",
      ],
    },
    DURING: {
      title: "During a Landslide",
      subtitle: "Immediate Survival & Escape Actions",
      dos: [
        "Quickly move away from the path of debris toward open, elevated ground away from cliff bases.",
        "If trapped indoors and escape is impossible, curl into a tight ball under sturdy furniture and protect your head.",
        "Listen for abnormal sounds: tree cracking, boulder tumbling, or rushing mud torrents.",
        "Alert nearby neighbors who may be in danger without placing yourself in direct harm.",
      ],
      donts: [
        "Do NOT attempt to cross roads covered with moving water, mud, or active falling rock debris.",
        "Do NOT shelter in river valleys, hollows, or lower-story rooms facing unstable embankments.",
        "Do NOT stand directly below steep cut-slopes during intense rainfall.",
      ],
    },
    AFTER: {
      title: "After a Landslide",
      subtitle: "Safe Recovery & Hazard Avoidance",
      dos: [
        "Stay away from the slide area. Secondary and tertiary slides frequently occur within 24–48 hours.",
        "Check for trapped or injured neighbors from a safe distance and report immediately to 112 or 1070.",
        "Inspect electrical wiring, LPG lines, and water pipes for damage before entering buildings.",
        "Listen to battery-powered radio or verified district administration updates.",
      ],
      donts: [
        "Do NOT drive over landslide-impacted roads until cleared and declared stable by highway engineers.",
        "Do NOT re-enter damaged buildings until certified safe by local municipal inspectors.",
        "Do NOT spread unverified social media rumors or unconfirmed casualties.",
      ],
    },
  };

  const naturalWarningSigns = [
    "Sudden appearance of muddy water springs, seeps, or wet ground where it is usually dry.",
    "New cracks, fissures, or outward bulges appearing in soil slopes, road asphalt, or house foundations.",
    "Soil pulling away from building foundations or retaining walls.",
    "Fences, utility poles, retaining walls, or trees tilting visibly downslope.",
    "Unusual loud roaring, rumbling, or cracking sounds coming from the hillside (indicating rapid rock/debris detachment).",
  ];

  const goBagItems = [
    "High-power LED flashlight / torch with extra batteries",
    "Sealed drinking water (at least 3 liters per family member)",
    "Non-perishable ready-to-eat dry food (biscuits, energy bars)",
    "First aid kit with antiseptic, bandages, scissors, and personal prescription medicines",
    "Fully charged portable power bank with charging cables",
    "Emergency whistle to signal search and rescue teams if trapped",
    "Waterproof pouch with government IDs, property papers, and cash",
    "Sturdy hiking boots and rain ponchos / waterproof jackets",
  ];

  const currentSection = sections[activeTab];
  const completedCount = Object.values(checkedKitItems).filter(Boolean).length;

  return (
    <div className="p-4 space-y-4">
      {/* Header Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-5 shadow-xl">
        <div className="flex items-center gap-2.5 text-indigo-400 mb-1">
          <BookOpen className="w-5 h-5" />
          <span className="text-[10px] font-mono uppercase font-black tracking-wider">
            OFFICIAL CITIZEN GUIDELINES
          </span>
        </div>
        <h1 className="text-lg font-black text-slate-100 uppercase tracking-tight">
          Landslide Safety & Survival Guide
        </h1>
        <p className="text-xs text-slate-400 mt-1 leading-relaxed">
          Standard safety protocols recommended by National & State Disaster Management Authorities for mountain communities in North Eastern India.
        </p>
      </div>

      {/* 1. Phase Tabs: BEFORE / DURING / AFTER */}
      <div className="grid grid-cols-3 bg-slate-900 p-1 rounded-2xl border border-slate-800 text-xs font-bold font-mono">
        {(["BEFORE", "DURING", "AFTER"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`py-2 rounded-xl transition ${
              activeTab === tab
                ? "bg-red-600 text-white shadow-md shadow-red-950/50"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* 2. DOs and DONTs Cards */}
      <section className="space-y-3">
        <div className="border-b border-slate-800 pb-2">
          <h2 className="text-sm font-black text-slate-100 uppercase">{currentSection.title}</h2>
          <p className="text-[11px] text-slate-400">{currentSection.subtitle}</p>
        </div>

        {/* DOs */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-2.5">
          <div className="text-xs font-bold font-mono uppercase text-emerald-400 flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4" />
            DOs (Recommended Actions)
          </div>
          <div className="space-y-2">
            {currentSection.dos.map((item, idx) => (
              <div
                key={idx}
                className="p-3 bg-emerald-950/20 border border-emerald-900/40 rounded-xl text-xs text-emerald-100 flex items-start gap-2.5 leading-relaxed"
              >
                <span className="w-4 h-4 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px] font-bold flex-shrink-0 mt-0.5">
                  ✓
                </span>
                <span>{item}</span>
              </div>
            ))}
          </div>
        </div>

        {/* DONTs */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-2.5">
          <div className="text-xs font-bold font-mono uppercase text-red-400 flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4" />
            DONTs (Things to Avoid)
          </div>
          <div className="space-y-2">
            {currentSection.donts.map((item, idx) => (
              <div
                key={idx}
                className="p-3 bg-red-950/20 border border-red-900/40 rounded-xl text-xs text-red-100 flex items-start gap-2.5 leading-relaxed"
              >
                <span className="w-4 h-4 rounded-full bg-red-600 text-white flex items-center justify-center text-[10px] font-bold flex-shrink-0 mt-0.5">
                  ✕
                </span>
                <span>{item}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 3. Natural Landslide Warning Signs */}
      <section className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
        <div className="flex items-center gap-2 text-xs font-bold font-mono uppercase text-amber-400">
          <Eye className="w-4 h-4" />
          Natural Warning Signs to Watch For
        </div>
        <div className="space-y-2">
          {naturalWarningSigns.map((sign, idx) => (
            <div
              key={idx}
              className="p-3 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 flex items-start gap-2.5 leading-relaxed"
            >
              <span className="text-amber-400 font-bold font-mono text-sm mt-0.5">•</span>
              <span>{sign}</span>
            </div>
          ))}
        </div>
      </section>

      {/* 4. Interactive Emergency "Go-Bag" Packing Checklist */}
      <section className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-bold font-mono uppercase text-slate-100">
            <Backpack className="w-4 h-4 text-red-400" />
            Emergency Go-Bag Checklist
          </div>
          <span className="text-[10px] font-mono font-bold bg-slate-800 text-slate-300 px-2 py-0.5 rounded-full">
            {completedCount} / {goBagItems.length} Packed
          </span>
        </div>
        <p className="text-[11px] text-slate-400 leading-normal">
          Tap items as you pack your household emergency backpack. This list remains saved on your phone even offline.
        </p>

        <div className="space-y-2 pt-1">
          {goBagItems.map((item, idx) => {
            const isChecked = !!checkedKitItems[item];
            return (
              <div
                key={idx}
                onClick={() => toggleKitItem(item)}
                className={`p-3 rounded-xl border text-xs flex items-center justify-between gap-3 cursor-pointer transition select-none ${
                  isChecked
                    ? "bg-emerald-950/30 border-emerald-800 text-slate-200 line-through opacity-80"
                    : "bg-slate-950 border-slate-800 text-slate-200 hover:border-slate-700"
                }`}
              >
                <span>{item}</span>
                <div
                  className={`w-5 h-5 rounded-md border flex items-center justify-center flex-shrink-0 ${
                    isChecked
                      ? "bg-emerald-600 border-emerald-500 text-white font-bold text-xs"
                      : "border-slate-700 bg-slate-900"
                  }`}
                >
                  {isChecked && "✓"}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Fast Help Links */}
      <div className="p-3 bg-slate-950 rounded-2xl border border-slate-800 flex items-center justify-between">
        <div className="text-xs text-slate-300">Need emergency assistance now?</div>
        <Link
          href="/citizen/sos"
          className="text-xs font-bold font-mono text-red-400 hover:text-red-300 flex items-center gap-1"
        >
          Open SOS <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
}
