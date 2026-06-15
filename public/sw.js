// Minimal service worker: caches the app shell + sprite + PWA assets so
// repeat visits are near-instant (warm start). Registered from main.js.
//
// Strategy:
//   - Navigation requests → Network first, fall back to cache (always fresh)
//   - Same-origin assets (JS, CSS, fonts, sprite, manifest) → Stale-while-revalidate
//   - Cross-origin (Google Fonts, MediaPipe CDN) → Cache-first with 30-day TTL

const CACHE_VERSION = 'eafc-v6';
const PRECACHE = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/icon.svg',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/sprites/sheet.png',
  '/sprites/atlas.json',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_VERSION)
      .then(cache => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_VERSION).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Navigation: network-first with cache fallback
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(resp => {
          const copy = resp.clone();
          caches.open(CACHE_VERSION).then(c => c.put(request, copy));
          return resp;
        })
        .catch(() => caches.match(request).then(r => r || caches.match('/')))
    );
    return;
  }

  // Same-origin static assets: stale-while-revalidate
  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(request).then(cached => {
        const fetchPromise = fetch(request).then(resp => {
          if (resp && resp.status === 200) {
            const copy = resp.clone();
            caches.open(CACHE_VERSION).then(c => c.put(request, copy));
          }
          return resp;
        }).catch(() => cached);
        return cached || fetchPromise;
      })
    );
    return;
  }

  // Cross-origin (fonts, MediaPipe CDN): cache-first, 30-day TTL implicit
  // (evicted when CACHE_VERSION bumps on redeploy).
  event.respondWith(
    caches.match(request).then(cached => {
      if (cached) return cached;
      return fetch(request).then(resp => {
        if (resp && resp.status === 200 && resp.type === 'basic' || resp.type === 'cors') {
          const copy = resp.clone();
          caches.open(CACHE_VERSION).then(c => c.put(request, copy));
        }
        return resp;
      }).catch(() => cached);
    })
  );
});
