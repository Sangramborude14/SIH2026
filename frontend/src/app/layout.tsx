import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DISASTRA - Disaster Intelligence Engine (NER Landslides)",
  description: "AI-Based Early Warning and Landslide Risk Monitoring System in the North Eastern Region",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased bg-slate-950 text-slate-100 min-h-screen">
        {children}
      </body>
    </html>
  );
}
