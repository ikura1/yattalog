// ホーム：タップで記録（楽観的更新、決定 028）、長押し、編集モード、並べ替え、左右スワイプ。
import { busy, isReloadPending, reloadIfNewBuild, reloadIfPending, whenBusy } from "./build.js";
import { $, $$, TOO_MANY, app, drain, post, store } from "./dom.js";
import { haptic, toast } from "./feedback.js";
import { loadSheet } from "./sheet.js";
import { swipeTab } from "./tabs.js";

/* ---------- ホーム：タップで記録・長押し・編集モード ---------- */
let editing = false;
let press = null;
const LONG = 480, SLOP = 10, EDGE = 20;

whenBusy(() => editing || press || $(".pending-net"));

function setEditing(on) {
  editing = on;
  app().classList.toggle("editing", on);
  const b = $("#editBtn");
  b.textContent = on ? "完了" : "編集";
  b.setAttribute("aria-pressed", String(on));
  $("#editHint").hidden = !on;
  if (!on) reloadIfPending();
}
export const toggleEditing = () => setEditing(!editing);

function replaceTile(li, html) {
  if (!html) return;
  const tpl = document.createElement("template");
  tpl.innerHTML = html.trim();
  const fresh = tpl.content.firstElementChild;
  fresh.hidden = li.hidden;
  li.replaceWith(fresh);
  return fresh;
}

// 数字を聞くイベントは、押すと数字のシートを開く（決定 074）。ほかは、そのまま記録する
const tapRecord = (t) => (t.dataset.numberUrl ? loadSheet(t.dataset.numberUrl) : quickRecord(t));
async function quickRecord(btn, logId = crypto.randomUUID()) {
  if (!navigator.onLine) { toast("オフラインです。つながると記録できます"); return; }
  const li = btn.closest("li");
  const before = li.outerHTML;
  // 楽観的更新：返事を待たずに「さっき」にする
  const ago = $(".ago", btn);
  if (ago) { ago.className = "ago"; ago.textContent = "さっき"; }
  btn.classList.add("today", "pop", "pending-net");
  haptic(12); // 押した瞬間の手ごたえ
  try {
    const res = await post(btn.dataset.recordUrl, { log_id: logId });
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    const fresh = replaceTile(li, data.tile_html);
    const fbtn = fresh && $(".tile", fresh);
    if (fbtn) fbtn.classList.add("stamp"); // サーバーに記録できた印（✓ が一瞬出る）
    if (data.streak_grew && fbtn) { const s = $(".streak", fbtn); if (s) s.classList.add("burst"); }
    const name = $(".name", fbtn || btn)?.textContent || "";
    // 記録した直後が、いちばん次の操作をしたい瞬間。取り消し・メモ・シェア・詳細へ、ここから行ける（決定 055）
    const said = data.streak_grew ? `🔥 ${data.streak_text}！` : `やった！ ${name} を記録しました`;
    toast(data.achievement ? `${said}　${data.achievement}` : said, [
      { label: "取り消す", fn: () => undo(data.log_id, fresh) },
      { label: "メモ", fn: () => loadSheet(`/logs/${data.log_id}/edit/`) },
      { label: "シェア", fn: () => loadSheet(data.share_url) },
      { label: "詳細", fn: () => { location.href = (fbtn || btn).dataset.detailUrl; } },
    ], { stack: true, duration: 7000 });
    if (!store.get("yl:hint-longpress")) {
      store.set("yl:hint-longpress", "1");
      setTimeout(() => toast("💡 タイルを長押しすると、日付を変えたりメモを残したりできます", [{ label: "OK", fn: () => {} }], { hint: true, duration: 9000 }), 5400);
    }
  } catch (err) {
    const restored = replaceTile($(`#grid > li[data-id="${li.dataset.id}"]`) || li, before);
    const retry = [{ label: "もう一度", fn: () => { const b = restored && $(".tile", restored); if (b) quickRecord(b, logId); } }];
    toast(err.message === "429" ? TOO_MANY : "記録できませんでした", retry);
  }
}

async function undo(logId, li) {
  try {
    const res = await post(`/logs/${logId}/undo/`, {});
    if (!res.ok) throw new Error();
    const data = await res.json();
    const cur = li && li.isConnected ? li : $(`#grid > li[data-id="${li?.dataset.id}"]`);
    if (cur && data.tile_html) replaceTile(cur, data.tile_html);
    toast("取り消しました");
  } catch (_) {
    toast("取り消せませんでした", [{ label: "もう一度", fn: () => undo(logId, li) }]);
  }
}

export function bindHome() {
  const grid = $("#grid");
  if (!grid || grid.dataset.bound) return;
  grid.dataset.bound = "1";

  grid.addEventListener("pointerdown", (e) => {
    const t = e.target.closest(".tile");
    if (!t || t.classList.contains("add") || (e.button && e.button !== 0)) return;
    press = { el: t, x: e.clientX, y: e.clientY, moved: false, long: false, pid: e.pointerId };
    if (!editing) {
      t.classList.add("pressing");
      press.timer = setTimeout(() => {
        if (!press) return;
        press.long = true;
        t.classList.remove("pressing");
        haptic(15);
        loadSheet(t.dataset.sheetUrl);
      }, LONG);
    }
  });
  grid.addEventListener("contextmenu", (e) => {
    const t = e.target.closest(".tile");
    if (!t || t.classList.contains("add")) return;
    e.preventDefault();
    if (press && press.long) return;
    if (press) { clearTimeout(press.timer); press.el.classList.remove("pressing"); press = null; }
    if (!editing) loadSheet(t.dataset.sheetUrl);
  });
  grid.addEventListener("click", (e) => {
    const t = e.target.closest(".tile");
    if (!t || t.classList.contains("add")) return;
    if (e.target.closest("[data-x]") && editing) { loadSheet(t.dataset.removeUrl); return; }
    // キーボード（Enter/Space）は detail=0 の click になる
    if (e.detail === 0) { editing ? (location.href = t.dataset.detailUrl) : tapRecord(t); }
  });
  grid.addEventListener("keydown", (e) => {
    const t = e.target.closest(".tile");
    if (t && !t.classList.contains("add") && (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10"))) {
      e.preventDefault();
      loadSheet(t.dataset.sheetUrl);
    }
  });
}

window.addEventListener("pointermove", (e) => {
  if (!press || e.pointerId !== press.pid) return;
  const dx = e.clientX - press.x, dy = e.clientY - press.y;
  if (!press.moved && Math.hypot(dx, dy) > SLOP) {
    press.moved = true;
    clearTimeout(press.timer);
    press.el.classList.remove("pressing");
    if (editing) startDrag(e);
  }
  if (press.drag) moveDrag(e);
});
window.addEventListener("pointerup", (e) => {
  if (!press || e.pointerId !== press.pid) return;
  const p = press;
  press = null;
  clearTimeout(p.timer);
  p.el.classList.remove("pressing");
  if (p.drag) { endDrag(p); return; }
  if (p.moved || p.long) return;
  if (e.target.closest && e.target.closest("[data-x]") && editing) return;
  if (editing) location.href = p.el.dataset.detailUrl;
  else tapRecord(p.el);
});
window.addEventListener("pointercancel", () => {
  if (!press) return;
  clearTimeout(press.timer);
  press.el.classList.remove("pressing");
  if (press.drag) endDrag(press);
  press = null;
});

// 並べ替え（編集モード）。動かしたあとの前後のイベントをサーバーに送る（分数インデックス）
function startDrag(e) {
  const r = press.el.getBoundingClientRect();
  const g = press.el.cloneNode(true);
  g.classList.add("ghost");
  g.style.width = r.width + "px";
  g.style.height = r.height + "px";
  document.body.appendChild(g);
  press.drag = { ghost: g, ox: e.clientX - r.left, oy: e.clientY - r.top, li: press.el.closest("li") };
  press.el.classList.add("dragging");
  window.getSelection()?.removeAllRanges();
  document.body.classList.add("sorting"); // ドラッグのあいだ、画面のどこでも文字を選ばせない
  moveDrag(e);
}
function moveDrag(e) {
  const d = press.drag;
  d.ghost.style.left = e.clientX - d.ox + "px";
  d.ghost.style.top = e.clientY - d.oy + "px";
  d.ghost.hidden = true;
  const over = document.elementFromPoint(e.clientX, e.clientY);
  d.ghost.hidden = false;
  const li = over && over.closest("#grid > li[data-id]");
  if (!li || li === d.li) return;
  const items = $$("#grid > li[data-id]");
  const from = items.indexOf(d.li), to = items.indexOf(li);
  li.parentNode.insertBefore(d.li, from < to ? li.nextSibling : li);
}
function endDrag(p) {
  p.drag.ghost.remove();
  p.el.classList.remove("dragging");
  document.body.classList.remove("sorting");
  const visible = $$("#grid > li[data-id]").filter((li) => !li.hidden);
  const i = visible.indexOf(p.drag.li);
  const before = visible[i - 1]?.dataset.id || "";
  const after = visible[i + 1]?.dataset.id || "";
  post(p.el.dataset.moveUrl, { before, after }).then(drain).then((r) => {
    if (!r.ok) { toast("並べ替えを保存できませんでした"); refreshHome(); }
  }).catch(() => { toast("並べ替えを保存できませんでした"); refreshHome(); });
}

export function refreshHome() {
  const a = app();
  if (a && a.dataset.gridUrl && window.htmx) {
    window.htmx.ajax("GET", a.dataset.gridUrl, { target: "#grid-wrap", swap: "innerHTML" });
  }
}

/* ---------- 開いたままでも経過時間を古くしない ----------
   「さっき」「N時間」「今日」は時間がたつと変わるので、画面に戻ってきたときと一定時間ごとにホームを読み直す。
   編集中・シートを開いている間・タイルを押している間・記録の送信中は、操作のじゃまになるので読み直さない。 */
const STALE_MS = 5 * 60 * 1000;
let gridLoadedAt = Date.now();
export function gridLoaded() {
  gridLoadedAt = Date.now();
}
export function refreshIfStale() {
  if (document.hidden || !$("#grid") || !navigator.onLine) return;
  if (busy()) return;
  if (isReloadPending()) { reloadIfNewBuild(); return; }
  if (Date.now() - gridLoadedAt < STALE_MS) return;
  refreshHome();
}

/* ---------- 左右スワイプでタブ切り替え（画面の端は除く、レビュー D5） ---------- */
let sw = null;
document.addEventListener("pointerdown", (e) => {
  if (!$("#grid") || editing || e.target.closest("#tabs, #sheet, .toast")) { sw = null; return; }
  if (e.clientX < EDGE || e.clientX > window.innerWidth - EDGE) { sw = null; return; }
  sw = { x: e.clientX, y: e.clientY, t: Date.now() };
});
document.addEventListener("pointerup", (e) => {
  if (!sw) return;
  const dx = e.clientX - sw.x, dy = e.clientY - sw.y, dt = Date.now() - sw.t;
  sw = null;
  if (Math.abs(dx) > 60 && Math.abs(dy) < Math.abs(dx) * 0.6 && dt < 700) swipeTab(dx < 0 ? 1 : -1);
});
