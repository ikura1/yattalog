// どのファイルからも使う、小さな道具（要素をさがす、端末に覚える、サーバーに送る）。
export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];
export const store = {
  get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* 保存できなくても動く */ } },
};
export const TOO_MANY = "操作が多すぎます。少し待ってから、もう一度お試しください"; // 429（レート制限）
const csrf = () => {
  const h = document.body.getAttribute("hx-headers");
  try { return JSON.parse(h)["X-CSRFToken"]; } catch (_) { return ""; }
};
// 応答の中身を使わない送信でも、中身は読み切る。ログイン中の応答はブラウザに保存させない（no-store）ので、
// 読まないと受け取りが終わらないまま残る
export const drain = (r) => { r.text().catch(() => {}); return r; };
export const post = (url, data) => fetch(url, {
  method: "POST",
  headers: { "X-CSRFToken": csrf(), "X-Requested-With": "fetch" },
  body: new URLSearchParams(data),
  credentials: "same-origin",
});
export const app = () => $("#app");
