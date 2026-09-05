"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Shield,
  Home,
  BookOpen,
  LifeBuoy,
  Camera,
  MapPin,
  Wifi,
  WifiOff,
  AlertOctagon,
  RefreshCw,
} from "lucide-react";
import { syncPendingQueue, getPendingSOS, getPendingReports } from "@/lib/citizenOfflineStorage";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function CitizenLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [isOnline, setIsOnline] = useState<boolean>(true);
  const [pendingCount, setPendingCount] = useState<number>(0);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [syncToast, setSyncToast] = useState<string | null>(null);

  // Monitor Network & PWA Service Worker
  useEffect(() => {
    if (typeof window !== "undefined") {
      setIsOnline(navigator.onLine);

      const updateOnlineStatus = () => {
        const online = navigator.onLine;
        setIsOnline(online);
        if (online) {
          triggerSync();
        }
      };

      window.addEventListener("online", updateOnlineStatus);
      window.addEventListener("offline", updateOnlineStatus);

      // Register Service Worker
      if ("serviceWorker" in navigator) {
        navigator.serviceWorker
          .register("/sw.js")
          .catch((err) => console.warn("PWA ServiceWorker registration error:", err));
      }

      // Check initial pending items count
      checkPendingItems();

      return () => {
        window.removeEventListener("online", updateOnlineStatus);
        window.removeEventListener("offline", updateOnlineStatus);
      };
    }
  }, []);

  const checkPendingItems = () => {
    const sosCount = getPendingSOS().length;
    const repCount = getPendingReports().length;
    setPendingCount(sosCount + repCount);
  };

  const triggerSync = async () => {
    setIsSyncing(true);
    try {
      const res = await syncPendingQueue(API_URL, (sosCount, repCount) => {
        const total = sosCount + repCount;
        if (total > 0) {
          setSyncToast(`Synced ${total} offline item(s) to emergency server.`);
          setTimeout(() => setSyncToast(null), 5000);
        }
      });
      checkPendingItems();
    } catch (err) {
      console.warn("Offline sync error", err);
    } finally {
      setIsSyncing(false);
    }
  };

  const navItems = [
    { href: "/citizen", label: "Status", icon: Home },
    { href: "/citizen/safety", label: "Safety Guide", icon: BookOpen },
    { href: "/citizen/sos", label: "SOS", icon: AlertOctagon, isSos: true },
    { href: "/citizen/report", label: "Report", icon: Camera },
    { href: "/citizen/shelters", label: "Shelters", icon: MapPin },
  ];

  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100 flex flex-col max-w-md sm:max-w-lg mx-auto shadow-2xl border-x border-slate-800 selection:bg-red-500 selection:text-white">
      {/* 1. Header Bar */}
      <header className="sticky top-0 z-50 bg-slate-900/95 backdrop-blur border-b border-slate-800 px-4 py-3 flex items-center justify-between shadow-md">
        <Link href="/citizen" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-red-600 to-amber-600 flex items-center justify-center text-white shadow-lg shadow-red-950/50">
            <Shield className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[10px] font-black tracking-widest uppercase text-red-400 font-mono flex items-center gap-1.5">
              <span>DISASTRA CITIZEN</span>
              <span>•</span>
              <span>NER INDIA</span>
            </div>
            <div className="text-xs font-extrabold text-slate-100 flex items-center gap-1.5">
              <span>Landslide Safety & SOS</span>
            </div>
          </div>
        </Link>

        {/* Network & Offline Queue Badge */}
        <div className="flex items-center gap-2">
          {pendingCount > 0 && (
            <button
              onClick={triggerSync}
              disabled={isSyncing || !isOnline}
              className="text-[10px] font-mono font-bold bg-amber-950/80 text-amber-300 px-2 py-1 rounded-md border border-amber-800 flex items-center gap-1 animate-pulse"
              title="Items stored on device waiting for network"
            >
              <RefreshCw className={`w-3 h-3 ${isSyncing ? "animate-spin" : ""}`} />
              <span>{pendingCount} Pending</span>
            </button>
          )}

          <div
            className={`px-2 py-1 rounded-md text-[10px] font-mono font-bold flex items-center gap-1 border ${
              isOnline
                ? "bg-emerald-950/60 text-emerald-300 border-emerald-800/80"
                : "bg-red-950/80 text-red-300 border-red-800 animate-pulse"
            }`}
          >
            {isOnline ? (
              <>
                <Wifi className="w-3 h-3" />
                <span>ONLINE</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3 h-3" />
                <span>OFFLINE</span>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Sync Toast */}
      {syncToast && (
        <div className="bg-emerald-600 text-white text-xs font-medium px-4 py-2 text-center animate-fade-in shadow-md">
          {syncToast}
        </div>
      )}

      {/* 2. Main Content Area */}
      <main className="flex-1 pb-24 overflow-y-auto">{children}</main>

      {/* 3. Mobile Fixed Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 bg-slate-900/95 backdrop-blur border-t border-slate-800/90 max-w-md sm:max-w-lg mx-auto">
        <div className="grid grid-cols-5 items-center px-1 py-1.5">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;

            if (item.isSos) {
              return (
                <div key={item.href} className="flex justify-center -mt-5">
                  <Link
                    href={item.href}
                    className="w-14 h-14 rounded-full bg-gradient-to-tr from-red-700 via-red-600 to-rose-500 text-white flex flex-col items-center justify-center shadow-xl shadow-red-950/80 border-2 border-slate-900 active:scale-95 transition-transform"
                    aria-label="Emergency SOS Beacon"
                  >
                    <AlertOctagon className="w-6 h-6 animate-pulse" />
                    <span className="text-[9px] font-black tracking-wider uppercase mt-0.5">SOS</span>
                  </Link>
                </div>
              );
            }

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex flex-col items-center justify-center py-1.5 px-1 rounded-xl transition ${
                  isActive
                    ? "text-red-400 font-bold"
                    : "text-slate-400 hover:text-slate-200 active:text-white"
                }`}
              >
                <Icon className={`w-5 h-5 ${isActive ? "text-red-400 scale-110" : ""}`} />
                <span className="text-[10px] mt-1 tracking-tight">{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
