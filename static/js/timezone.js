// 端末のタイムゾーンが、設定と違うときの確認。
import { $, app, drain, post } from "./dom.js";
import { toast } from "./feedback.js";
import { refreshHome } from "./home.js";

/* ---------- タイムゾーン（決定 023） ---------- */
export function initTimezone() {
  const a = app();
  if (!a || !a.dataset.tzUrl) return;
  let device = "";
  try { device = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (_) { return; }
  if (!device) return;
  if (a.dataset.needsTz) {
    post(a.dataset.tzUrl, { tz: device, action: "set" }).then(drain).then((r) => { if (r.ok) a.dataset.userTz = device; });
    return;
  }
  if (device === a.dataset.userTz || device === a.dataset.keptTz) return;
  const b = $("#tzBanner");
  $("#tzName").textContent = device;
  b.hidden = false;
  $("#tzYes").onclick = () => post(a.dataset.tzUrl, { tz: device, action: "set" }).then(drain).then(() => { b.hidden = true; refreshHome(); toast(`タイムゾーンを ${device} にしました`); });
  $("#tzNo").onclick = () => post(a.dataset.tzUrl, { tz: device, action: "keep" }).then(drain).then(() => { b.hidden = true; });
}
