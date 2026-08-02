// ORBIS FINAI — offline-first service worker
const CACHE = "orbis-v1";
const ASSETS = [
  "/",
  "/manifest.json",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Stale-while-revalidate: hızlı yükleme + canlı veri
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  // API çağrıları: sadece ağ (canlı veri kritik)
  if (url.pathname.startsWith("/api/")) return;

  e.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(e.request);
      const network = fetch(e.request)
        .then((res) => {
          if (res && res.ok && url.origin === location.origin) cache.put(e.request, res.clone());
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
