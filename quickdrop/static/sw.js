/* QuickDrop Service Worker —— 缓存静态外壳，API 直连不缓存 */
const CACHE = "quickdrop-v1";
const ASSETS = [
  "/",
  "/static/style.css",
  "/static/app.js",
  "/static/icon-192.png",
  "/static/icon-512.png",
  "/manifest.json"
];

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      return c.addAll(ASSETS);
    }).catch(function () { /* 个别资源缺失不阻断安装 */ })
  );
  self.skipWaiting();
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", function (e) {
  const req = e.request;
  if (req.method !== "GET") return;                 // 上传等非 GET 直连
  const url = new URL(req.url);
  if (url.pathname.startsWith("/api/")) return;     // API 不缓存，避免陈旧数据
  e.respondWith(caches.match(req).then(function (r) { return r || fetch(req); }));
});
