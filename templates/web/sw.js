// Yattalog の Service Worker（決定 049）。
// しまっておくのは、だれが見ても同じもの（静的ファイルと、オフラインの案内）だけ。
// ログインした人の画面は、キャッシュに入れない（共用の端末で、ほかの人に見えてしまうため）。
const VERSION = "{{ version }}";
const CACHE = `yattalog-${VERSION}`;
const PRECACHE = [{% for url in precache %}"{{ url }}"{% if not forloop.last %}, {% endif %}{% endfor %}];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

// 版が変わったら、古いキャッシュを捨てる
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  // 記録などの書き込みと、よそのサイトへの通信には、手を出さない
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  // 画面の移動：必ずネットワークに取りに行く。つながらないときだけ、オフラインの案内を出す
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match("/offline/")));
    return;
  }

  // 静的ファイル：名前に中身のハッシュが入っているので、しまってあるものをそのまま使ってよい
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then((hit) => hit || fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      }))
    );
  }
  // それ以外（一覧の読み直しなど）は、ブラウザに任せる
});
