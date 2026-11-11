// Yattalog のクライアント側の入口。機能ごとのファイルを読み込み、htmx の合図とつなぐ（決定 070）。
import { reloadIfNewBuild, setBootScript } from "./build.js";
import { bindCategorySort } from "./categories.js";
import { bindSeason, bindTend } from "./detail.js";
import { $, TOO_MANY } from "./dom.js";
import { bindEmojiField } from "./emoji.js";
import { toast } from "./feedback.js";
import { bindHome, gridLoaded, refreshHome, refreshIfStale, toggleEditing } from "./home.js";
import { initInstall } from "./install.js";
import { bindRecordForm } from "./record-form.js";
import { bindShare } from "./share.js";
import { closeSheet, openSheet, sheet, sheetLoaded, sheetLoading } from "./sheet.js";
import { applyTab, currentTab } from "./tabs.js";
import { applyTheme, bindThemePreview, keepTheme, revertThemePreview } from "./theme.js";
import { initTimezone } from "./timezone.js";

setBootScript(import.meta.url); // 本番は、名前に中身のハッシュが入る

const netBanner = () => { const b = $("#netBanner"); if (b) b.hidden = navigator.onLine; };

/* ---------- htmx との連携 ---------- */
document.addEventListener("htmx:afterSwap", (e) => {
  const t = e.detail.target;
  if (t.id === "sheet-body") { revertThemePreview(); openSheet(); bindThemePreview(t); bindRecordForm(t); bindEmojiField(t); bindShare(t); bindCategorySort(t); }
  if (t.id === "grid-wrap") { gridLoaded(); bindHome(); applyTab(currentTab()); reloadIfNewBuild(); }
  if (t.id === "detail") { bindSeason(t); bindTend(t); }
});
// カテゴリのタブを開いているときは、追加フォームでそのカテゴリを選んでおく
document.addEventListener("htmx:configRequest", (e) => {
  if (e.detail.elt.id !== "addTile") return;
  const tab = $('#tabs [aria-selected="true"]')?.dataset.tab;
  if (tab && tab !== "all") e.detail.parameters.category = tab; // "none" も送る。サーバーが「なし」として扱う
});
// ページが切り替わるまで少しかかる送信（ログアウトなど）は、押した瞬間にボタンの文言を変えて、二度押しを防ぐ
document.addEventListener("submit", (e) => {
  const form = e.target.closest("form[data-busy]");
  const btn = form && $("button[type=submit]", form);
  if (!btn) return;
  btn.textContent = form.dataset.busy;
  btn.setAttribute("aria-busy", "true");
  setTimeout(() => { btn.disabled = true; }, 0); // 送信が始まってから無効にする（先に無効にすると、送られない）
});

// 設定を保存したら、見た目と震えをその場で変える（決定 066）
document.addEventListener("yl:prefs", (e) => {
  const { theme, haptics } = e.detail || {};
  keepTheme();
  applyTheme(theme);
  if (haptics === false) document.body.dataset.haptics = "0";
  else delete document.body.dataset.haptics;
});
document.addEventListener("yl:close-sheet", closeSheet);
document.addEventListener("yl:toast", (e) => toast(e.detail.message));
document.addEventListener("yl:go-home", () => { if (!$("#grid")) location.href = "/"; });
document.addEventListener("yl:changed", () => {
  if ($("#grid")) { refreshHome(); return; }
  const d = $("#detail");
  if (d && window.htmx) window.htmx.ajax("GET", location.pathname + location.search, { target: "#detail", swap: "innerHTML" });
});
const toSheet = (e) => e.detail.target && e.detail.target.id === "sheet-body";
document.addEventListener("htmx:beforeRequest", (e) => { if (toSheet(e) && e.detail.requestConfig?.verb === "get") sheetLoading(); });
document.addEventListener("htmx:afterRequest", (e) => { if (toSheet(e)) sheetLoaded(e.detail.successful); });
document.addEventListener("htmx:responseError", (e) => toast(e.detail.xhr && e.detail.xhr.status === 429 ? TOO_MANY : "うまくいきませんでした。もう一度お試しください"));
document.addEventListener("htmx:sendError", () => toast("通信できませんでした。つながっているか確認してください"));
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && sheet() && !sheet().hidden) closeSheet(); });

document.addEventListener("DOMContentLoaded", () => {
  const scrim = $("#scrim");
  if (scrim) scrim.addEventListener("click", closeSheet);
  const editBtn = $("#editBtn");
  if (editBtn) editBtn.addEventListener("click", toggleEditing);
  $("#tabs")?.closest("#grid-wrap")?.addEventListener("click", (e) => {
    const b = e.target.closest("[data-tab]");
    if (b) applyTab(b.dataset.tab);
  });
  bindHome();
  applyTab(currentTab());
  bindSeason(document);
  bindTend(document);
  initTimezone();
  initInstall();
  // オフラインのときに案内を出し、静的ファイルをしまっておく（決定 049）。失敗しても、アプリはそのまま動く
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  netBanner();
  document.addEventListener("visibilitychange", refreshIfStale);
  setInterval(refreshIfStale, 60 * 1000);
  window.addEventListener("online", netBanner);
  window.addEventListener("offline", netBanner);
});
