/**
 * SIH26001 Platform Data Formatting Utilities
 * Eliminates serialization bugs like [object Object] and formats telemetry,
 * angles, elevations, risks, and timestamps in a typed, consistent manner.
 */

export function formatFactorTelemetry(rawValue: any, factorName?: string): string {
  if (rawValue === null || rawValue === undefined) {
    return "--";
  }

  // Case 1: Simple numeric value
  if (typeof rawValue === "number") {
    if (isNaN(rawValue)) return "--";
    const nameLower = (factorName || "").toLowerCase();
    if (nameLower.includes("rain") || nameLower.includes("precipitation")) {
      return `${rawValue.toFixed(1)} mm`;
    }
    if (nameLower.includes("soil") || nameLower.includes("saturation") || nameLower.includes("moisture")) {
      return `${rawValue.toFixed(1)}%`;
    }
    if (nameLower.includes("slope") || nameLower.includes("angle")) {
      return `${rawValue.toFixed(1)}°`;
    }
    if (nameLower.includes("elevation")) {
      return `${rawValue.toFixed(0)}m`;
    }
    return rawValue.toFixed(1);
  }

  // Case 2: Structured dictionary for Terrain & Slope Angle
  if (typeof rawValue === "object" && !Array.isArray(rawValue)) {
    // Terrain dictionary: { slope_angle, elevation, aspect }
    if ("slope_angle" in rawValue || "elevation" in rawValue) {
      const slope = rawValue.slope_angle !== undefined ? `${Number(rawValue.slope_angle).toFixed(1)}°` : null;
      const elev = rawValue.elevation !== undefined ? `${Number(rawValue.elevation).toFixed(0)}m` : null;
      const aspect = rawValue.aspect ? `${rawValue.aspect}` : null;
      return [slope, elev, aspect].filter(Boolean).join(" • ");
    }

    // Historical dictionary: { historical_events, susceptibility }
    if ("historical_events" in rawValue || "susceptibility" in rawValue) {
      const events = rawValue.historical_events !== undefined ? `${rawValue.historical_events} events` : "";
      const susc = rawValue.susceptibility !== undefined ? `Score ${Number(rawValue.susceptibility).toFixed(1)}` : "";
      return [events, susc].filter(Boolean).join(" • ");
    }

    // Generic key-value dictionary
    try {
      return Object.entries(rawValue)
        .map(([k, v]) => {
          const valStr = typeof v === "number" ? v.toFixed(1) : String(v);
          return `${k.replace(/_/g, " ")}: ${valStr}`;
        })
        .join(", ");
    } catch {
      return "--";
    }
  }

  // Case 3: Array of values
  if (Array.isArray(rawValue)) {
    return rawValue.join(", ");
  }

  // Case 4: String
  return String(rawValue);
}

export function formatRiskScore(score: number | null | undefined): string {
  if (score === null || score === undefined || isNaN(score)) return "0.0";
  return score.toFixed(1);
}

export function formatProbability(prob: number | null | undefined): string {
  if (prob === null || prob === undefined || isNaN(prob)) return "--";
  return `${(prob * 100).toFixed(1)}%`;
}

export function formatRainfall(mm: number | null | undefined): string {
  if (mm === null || mm === undefined || isNaN(mm)) return "0.0 mm";
  return `${mm.toFixed(1)} mm`;
}

export function formatSlope(deg: number | null | undefined): string {
  if (deg === null || deg === undefined || isNaN(deg)) return "0.0°";
  return `${deg.toFixed(1)}°`;
}

export function formatElevation(meters: number | null | undefined): string {
  if (meters === null || meters === undefined || isNaN(meters)) return "0 m";
  return `${Math.round(meters)} m`;
}
