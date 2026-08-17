const CACHE_NAME = 'dadchelor-v0817-1116';
const ASSETS = [
  '/',
  '/index.html',
  '/dadchelor_v2.html',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png'
];

// Install: cache core assets
self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate: clear old caches
self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE_NAME; })
            .map(function(k) { return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

// Fetch: network first, fall back to cache
self.addEventListener('fetch', function(e) {
  // Skip non-GET and Supabase API calls (always need fresh data)
  if (e.request.method !== 'GET' || e.request.url.includes('supabase.co')) {
    return;
  }
  e.respondWith(
    fetch(e.request)
      .then(function(response) {
        // Cache successful responses
        if (response && response.status === 200) {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(e.request, clone);
          });
        }
        return response;
      })
      .catch(function() {
        // Network failed, try cache
        return caches.match(e.request);
      })
  );
});
