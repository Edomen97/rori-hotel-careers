/* ============================================
   SERVICE WORKER (sw.js)
   Rori Hotel Careers Portal
   ============================================ */

const CACHE_NAME = 'rori-careers-v1';

// Static core assets to pre-cache
const STATIC_ASSETS = [
    '/',
    '/jobs',
    '/static/css/main.css',
    '/static/css/careers.css',
    '/static/css/jobs.css',
    '/static/js/main.js',
    '/static/js/wizard.js',
    '/static/images/logo.png'
];

// ===== INSTALL EVENT =====
self.addEventListener('install', (event) => {
    self.skipWaiting(); // Immediately activate the new service worker
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(STATIC_ASSETS))
            .catch((error) => console.error('[SW] Cache pre-fetch failed:', error))
    );
});

// ===== ACTIVATE EVENT (CACHE CLEANUP) =====
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((cache) => cache !== CACHE_NAME)
                    .map((cache) => caches.delete(cache))
            );
        }).then(() => self.clients.claim()) // Take control of all open pages immediately
    );
});

// ===== FETCH EVENT =====
self.addEventListener('fetch', (event) => {
    const request = event.request;

    // Only handle GET requests (bypass POST, PUT, DELETE form submissions)
    if (request.method !== 'GET') return;

    const url = new URL(request.url);

    // Strategy 1: Cache-First for static assets (/static/)
    if (url.origin === location.origin && url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(request).then((cachedResponse) => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                return fetch(request).then((networkResponse) => {
                    if (networkResponse && networkResponse.status === 200) {
                        const responseClone = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(request, responseClone));
                    }
                    return networkResponse;
                });
            })
        );
        return;
    }

    // Strategy 2: Network-First with Cache Fallback for dynamic page routes
    event.respondWith(
        fetch(request)
            .then((networkResponse) => {
                if (networkResponse && networkResponse.status === 200) {
                    const responseClone = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(request, responseClone));
                }
                return networkResponse;
            })
            .catch(() => {
                return caches.match(request).then((cachedResponse) => {
                    return cachedResponse || caches.match('/');
                });
            })
    );
});
