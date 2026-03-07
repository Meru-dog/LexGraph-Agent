// Placeholder so GET /sw.js returns 200 and avoids 404 (no active service worker behavior).
self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function () { self.clients.claim(); });
