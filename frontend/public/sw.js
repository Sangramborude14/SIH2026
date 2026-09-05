// Service Worker for DISASTRA Citizen PWA
const CACHE_NAME = "disastra-citizen-v1";
const OFFLINE_URLS = [
  "/citizen",
  "/citizen/safety",
  "/citizen/shelters",
  "/citizen/sos",
  "/citizen/report",
  "/manifest.json",
];

// Install: Cache offline essential pages
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(OFFLINE_URLS).catch((err) => {
        console.warn("Pre-caching offline routes warning:", err);
      });
    })
  );
  self.skipWaiting();
});

// Activate: Cleanup old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch: Stale-while-revalidate for pages, network-first for APIs
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Do not cache API endpoints with service worker; client-side queue handles offline data
  if (url.pathname.startsWith("/api/")) {
    return;
  }

  // Stale-while-revalidate strategy for UI pages and static files
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      const fetchPromise = fetch(event.request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200 && event.request.method === "GET") {
            const responseToCache = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, responseToCache);
            });
          }
          return networkResponse;
        })
        .catch(() => {
          // If offline and not in cache, fallback to main citizen offline page
          return cachedResponse;
        });

      return cachedResponse || fetchPromise;
    })
  );
});
