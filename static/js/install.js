// ホーム画面への追加（PWA）の案内。
import { $, app, store } from "./dom.js";
import { loadSheet } from "./sheet.js";

/* ---------- ホーム画面への追加（PWA）の案内（SPEC 3.13、決定 031・043） ----------
   閉じたら7日間は出さない。3回閉じたら、それ以降は出さない。端末ごとの話なので、ブラウザのストレージで数える。 */
const INSTALL_KEY = "yl:install";
const INSTALL_SNOOZE_MS = 7 * 24 * 60 * 60 * 1000;
const INSTALL_MAX_DISMISS = 3;
let installPrompt = null; // Android などで、ブラウザが「追加できる」と知らせてきたときの合図
const isStandalone = () => window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
function installPlatform() {
  const ua = navigator.userAgent;
  const ios = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  if (ios) return /CriOS|FxiOS|EdgiOS|OPiOS/.test(ua) ? "ios-other" : "ios";
  return /Android/.test(ua) ? "android" : "";
}
function installState() {
  try { return JSON.parse(store.get(INSTALL_KEY)) || {}; } catch (_) { return {}; }
}
function showInstallBanner() {
  const b = $("#installBanner");
  if (!b || isStandalone()) return;
  const st = installState();
  if ((st.count || 0) >= INSTALL_MAX_DISMISS || (st.until || 0) > Date.now()) return;
  // iOS はブラウザから合図が来ないので、端末を見て出す。それ以外は、合図が来たとき（＝追加できるとき）だけ出す
  if (!installPrompt && !installPlatform().startsWith("ios")) return;
  b.hidden = false;
}
function openInstallGuide() {
  const a = app();
  loadSheet(`${(a && a.dataset.installUrl) || "/install/"}?p=${installPlatform()}`);
}
export function initInstall() {
  const b = $("#installBanner");
  if (!b) return;
  $("#installYes").onclick = async () => {
    if (!installPrompt) { openInstallGuide(); return; }
    const prompt = installPrompt;
    installPrompt = null;
    prompt.prompt(); // ブラウザの追加ダイアログを開く
    try { await prompt.userChoice; } catch (_) { /* 閉じられても何もしない */ }
    b.hidden = true;
  };
  $("#installNo").onclick = () => {
    const st = installState();
    store.set(INSTALL_KEY, JSON.stringify({ count: (st.count || 0) + 1, until: Date.now() + INSTALL_SNOOZE_MS }));
    b.hidden = true;
  };
  showInstallBanner();
}
window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); installPrompt = e; showInstallBanner(); });
window.addEventListener("appinstalled", () => { const b = $("#installBanner"); if (b) b.hidden = true; });document.addEventListener("click", (e) => {
  if (e.target.closest("#menuInstall")) openInstallGuide();
});
