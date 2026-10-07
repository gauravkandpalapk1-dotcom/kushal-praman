/* Kaushal Pramaan app-shell service worker.
 *
 * Goal: a candidate who opened the app once while online can reload and capture evidence with
 * zero signal. Evidence itself never goes through this cache; it lives in the encrypted
 * IndexedDB queue.
 *
 *  - install:   precache the candidate routes and every /_next/static asset they reference
 *  - /_next/static/*  cache-first (content-hashed, immutable)
 *  - navigations      network-first, falling back to the cached page, then the cached /candidate shell
 *  - /api/v1/qualifications*  network-first with cache fallback (QP/NOS/PC readable offline)
 *  - all other /api   network only
 */
const VERSION = "kp-shell-v1";
const SHELL_ROUTES = ["/", "/login", "/candidate", "/candidate/capture", "/research"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(VERSION);
      const assets = new Set();
      for (const route of SHELL_ROUTES) {
        try {
          const res = await fetch(route, { cache: "no-cache" });
          if (!res.ok) continue;
          await cache.put(route, res.clone());
          const html = await res.text();
          for (const m of html.matchAll(/\/_next\/static\/[^"'\s)]+/g)) assets.add(m[0]);
        } catch (_) {
          /* best effort */
        }
      }
      await Promise.all(
        [...assets, "/manifest.webmanifest", "/icon.svg"].map((u) => cache.add(u).catch(() => undefined)),
      );
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      for (const key of await caches.keys()) if (key !== VERSION) await caches.delete(key);
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/_next/static/")) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            const copy = res.clone();
            caches.open(VERSION).then((c) => c.put(req, copy));
            return res;
          }),
      ),
    );
    return;
  }

  if (url.pathname.startsWith("/api/v1/qualifications")) {
    event.respondWith(networkFirst(req));
    return;
  }
  if (url.pathname.startsWith("/api/")) return;

  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(url.pathname, copy));
          return res;
        })
        .catch(async () => (await caches.match(url.pathname)) || (await caches.match("/candidate")) || Response.error()),
    );
  }
});

async function networkFirst(req) {
  try {
    const res = await fetch(req);
    if (res.ok) {
      const copy = res.clone();
      caches.open(VERSION).then((c) => c.put(req, copy));
    }
    return res;
  } catch (_) {
    return (await caches.match(req)) || Response.error();
  }
}
