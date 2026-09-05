/**
 * Citizen Offline Storage & Media Optimization Utility
 * 
 * 1. Resizes & compresses camera images client-side via HTML5 Canvas to <400KB,
 *    stripping EXIF metadata to preserve privacy and enable rapid upload on 2G/3G mountain links.
 * 2. Queues SOS distress signals and Citizen Reports when the user is disconnected.
 * 3. Maintains honest state transparency: Items in queue explicitly have status
 *    "PENDING — WAITING FOR NETWORK" (never falsely "SENT").
 */

export interface PendingSOSItem {
  id: string;
  emergency_type: string;
  latitude: number;
  longitude: number;
  location_accuracy?: number;
  location_name?: string;
  contact_name?: string;
  contact_phone?: string;
  num_people: number;
  message?: string;
  created_at: string;
  status: "PENDING_NETWORK";
}

export interface PendingReportItem {
  id: string;
  category: string;
  description: string;
  latitude?: number;
  longitude?: number;
  location_accuracy?: number;
  location_name?: string;
  contact_phone?: string;
  imageBase64?: string;
  imageFileName?: string;
  imageMimeType?: string;
  created_at: string;
  status: "PENDING_NETWORK";
}

const SOS_QUEUE_KEY = "disastra_citizen_pending_sos";
const REPORT_QUEUE_KEY = "disastra_citizen_pending_reports";

/**
 * Client-side canvas downsampling and compression.
 * Strips EXIF metadata by re-rendering pixel data onto a clean canvas.
 */
export async function compressImageClientSide(
  file: File,
  maxDimension: number = 1280,
  quality: number = 0.75
): Promise<{ blob: Blob; compressedFile: File; previewUrl: string; sizeReductionPct: number }> {
  return new Promise((resolve, reject) => {
    const originalSize = file.size;
    const reader = new FileReader();

    reader.onload = (event) => {
      const img = new Image();
      img.onload = () => {
        let width = img.width;
        let height = img.height;

        // Calculate aspect ratio scale
        if (width > maxDimension || height > maxDimension) {
          if (width > height) {
            height = Math.round((height * maxDimension) / width);
            width = maxDimension;
          } else {
            width = Math.round((width * maxDimension) / height);
            height = maxDimension;
          }
        }

        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;

        const ctx = canvas.getContext("2d");
        if (!ctx) {
          reject(new Error("Unable to create HTML5 canvas context for compression"));
          return;
        }

        // Draw image onto clean canvas (effectively strips all EXIF metadata)
        ctx.drawImage(img, 0, 0, width, height);

        canvas.toBlob(
          (blob) => {
            if (!blob) {
              reject(new Error("Image compression failed"));
              return;
            }

            const newSize = blob.size;
            const sizeReductionPct = originalSize > 0
              ? Math.max(0, Math.round(((originalSize - newSize) / originalSize) * 100))
              : 0;

            const compressedFile = new File([blob], file.name.replace(/\.[^/.]+$/, ".jpg"), {
              type: "image/jpeg",
              lastModified: Date.now(),
            });

            const previewUrl = URL.createObjectURL(blob);

            resolve({
              blob,
              compressedFile,
              previewUrl,
              sizeReductionPct,
            });
          },
          "image/jpeg",
          quality
        );
      };

      img.onerror = () => reject(new Error("Failed to decode image file"));
      img.src = event.target?.result as string;
    };

    reader.onerror = () => reject(new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}

/**
 * Queue an SOS distress signal when device is offline.
 */
export function queueOfflineSOS(item: Omit<PendingSOSItem, "id" | "created_at" | "status">): PendingSOSItem {
  const pendingItem: PendingSOSItem = {
    ...item,
    id: `local_sos_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    created_at: new Date().toISOString(),
    status: "PENDING_NETWORK",
  };

  if (typeof window !== "undefined") {
    try {
      const existing = getPendingSOS();
      existing.push(pendingItem);
      localStorage.setItem(SOS_QUEUE_KEY, JSON.stringify(existing));
    } catch (e) {
      console.error("Failed to write to local storage", e);
    }
  }

  return pendingItem;
}

/**
 * Get all offline queued SOS signals.
 */
export function getPendingSOS(): PendingSOSItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(SOS_QUEUE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error("Failed to read pending SOS", e);
    return [];
  }
}

/**
 * Remove an SOS item from the queue after successful upload.
 */
export function removePendingSOS(id: string): void {
  if (typeof window === "undefined") return;
  try {
    const items = getPendingSOS().filter((i) => i.id !== id);
    localStorage.setItem(SOS_QUEUE_KEY, JSON.stringify(items));
  } catch (e) {
    console.error("Failed to remove pending SOS", e);
  }
}

/**
 * Queue a Citizen Hazard Report when offline.
 */
export function queueOfflineReport(item: Omit<PendingReportItem, "id" | "created_at" | "status">): PendingReportItem {
  const pendingItem: PendingReportItem = {
    ...item,
    id: `local_rep_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    created_at: new Date().toISOString(),
    status: "PENDING_NETWORK",
  };

  if (typeof window !== "undefined") {
    try {
      const existing = getPendingReports();
      existing.push(pendingItem);
      localStorage.setItem(REPORT_QUEUE_KEY, JSON.stringify(existing));
    } catch (e) {
      console.error("Failed to write report to local storage", e);
    }
  }

  return pendingItem;
}

/**
 * Get all offline queued hazard reports.
 */
export function getPendingReports(): PendingReportItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(REPORT_QUEUE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error("Failed to read pending reports", e);
    return [];
  }
}

/**
 * Remove a report from queue after successful upload.
 */
export function removePendingReport(id: string): void {
  if (typeof window === "undefined") return;
  try {
    const items = getPendingReports().filter((i) => i.id !== id);
    localStorage.setItem(REPORT_QUEUE_KEY, JSON.stringify(items));
  } catch (e) {
    console.error("Failed to remove pending report", e);
  }
}

/**
 * Convert dataURL to Blob for multipart network upload.
 */
export function dataURItoBlob(dataURI: string): Blob {
  const byteString = atob(dataURI.split(",")[1]);
  const mimeString = dataURI.split(",")[0].split(":")[1].split(";")[0];
  const ab = new ArrayBuffer(byteString.length);
  const ia = new Uint8Array(ab);
  for (let i = 0; i < byteString.length; i++) {
    ia[i] = byteString.charCodeAt(i);
  }
  return new Blob([ab], { type: mimeString });
}

/**
 * Background synchronizer that flushes queued offline SOS and reports when network returns.
 */
export async function syncPendingQueue(
  apiUrl: string,
  onSyncComplete?: (syncedSOS: number, syncedReports: number) => void
): Promise<{ syncedSOS: number; syncedReports: number }> {
  let syncedSOS = 0;
  let syncedReports = 0;

  if (typeof window === "undefined" || !navigator.onLine) {
    return { syncedSOS, syncedReports };
  }

  // 1. Sync Pending SOS
  const pendingSOS = getPendingSOS();
  for (const item of pendingSOS) {
    try {
      const res = await fetch(`${apiUrl}/api/v1/citizen/sos`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          emergency_type: item.emergency_type,
          latitude: item.latitude,
          longitude: item.longitude,
          location_accuracy: item.location_accuracy,
          location_name: item.location_name,
          contact_name: item.contact_name,
          contact_phone: item.contact_phone,
          num_people: item.num_people,
          message: item.message,
          device_fingerprint: item.id,
        }),
      });
      if (res.ok) {
        removePendingSOS(item.id);
        syncedSOS++;
      }
    } catch (err) {
      console.warn("Failed to sync offline SOS item:", item.id, err);
    }
  }

  // 2. Sync Pending Reports
  const pendingReports = getPendingReports();
  for (const rep of pendingReports) {
    try {
      const formData = new FormData();
      formData.append("category", rep.category);
      formData.append("description", rep.description);
      if (rep.latitude) formData.append("latitude", rep.latitude.toString());
      if (rep.longitude) formData.append("longitude", rep.longitude.toString());
      if (rep.location_accuracy) formData.append("location_accuracy", rep.location_accuracy.toString());
      if (rep.location_name) formData.append("location_name", rep.location_name);
      if (rep.contact_phone) formData.append("contact_phone", rep.contact_phone);

      if (rep.imageBase64) {
        const blob = dataURItoBlob(rep.imageBase64);
        formData.append("photo", blob, rep.imageFileName || "report.jpg");
      }

      const res = await fetch(`${apiUrl}/api/v1/citizen/report`, {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        removePendingReport(rep.id);
        syncedReports++;
      }
    } catch (err) {
      console.warn("Failed to sync offline report:", rep.id, err);
    }
  }

  if (onSyncComplete && (syncedSOS > 0 || syncedReports > 0)) {
    onSyncComplete(syncedSOS, syncedReports);
  }

  return { syncedSOS, syncedReports };
}
