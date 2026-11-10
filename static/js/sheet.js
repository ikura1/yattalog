// 下からせり上がるシート。中身は htmx が入れる。
import { reloadIfPending, whenBusy } from "./build.js";
import { $ } from "./dom.js";
import { revertThemePreview } from "./theme.js";

/* ---------- シート ---------- */
export const sheet = () => $("#sheet");
export function openSheet() {
  sheet().hidden = false;
  sheet().scrollTop = 0; // 中身が入れ替わったら、一番上から見せる（前のシートのスクロール位置を引き継がない）
  $("#scrim").hidden = false;
  // 入力欄には当てない（スマホでキーボードが開いて中身を隠すため）。読み上げのためにシート自体へ移す
  sheet().focus({ preventScroll: true });
}
export function closeSheet() {
  if (!sheet()) return;
  clearTimeout(sheetWait);
  revertThemePreview(); // 見た目を試したまま、保存せずに閉じたら元に戻す
  sheet().hidden = true;
  $("#scrim").hidden = true;
  $("#sheet-body").innerHTML = "";
  reloadIfPending(); // シートを開いている間に見送った読み込み直しを、ここで行う
}
// 押してからサーバーの返事が届くまでの間も、反応が見えるようにする（2026-10-20）。
// 閉じているときは、すぐに「読み込み中」のシートを開く。開いているときは、いまの中身を薄くする。
// すぐに返事が来たときにちらつかないよう、少しだけ待ってから出す
let sheetWait = 0;
const SHEET_WAIT_MS = 80;
export function sheetLoading() {
  clearTimeout(sheetWait);
  sheetWait = setTimeout(() => {
    const body = $("#sheet-body");
    if (sheet().hidden) {
      body.innerHTML = '<div class="sheet-loading" role="status"><span class="sr-only">読み込み中</span><i></i><i></i><i></i></div>';
      openSheet();
    } else body.classList.add("loading");
  }, SHEET_WAIT_MS);
}
export function sheetLoaded(ok) {
  clearTimeout(sheetWait);
  $("#sheet-body").classList.remove("loading");
  if (!ok && $("#sheet-body .sheet-loading")) closeSheet(); // 届かなければ、空のシートを残さない（知らせは別に出る）
}

export function loadSheet(url) {
  if (window.htmx) window.htmx.ajax("GET", url, { target: "#sheet-body" });
}
whenBusy(() => sheet() && !sheet().hidden); // 開いている間は、画面を読み込み直さない
document.addEventListener("click", (e) => {
  if (e.target.closest("[data-close-sheet]")) closeSheet();
});
