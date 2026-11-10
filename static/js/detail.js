// イベント詳細の「よくやる」（時期・曜日・時間帯・日にち）。
import { $, $$, store } from "./dom.js";

/* ---------- 詳細：よくやる時期のツールチップ ---------- */
export function bindSeason(root) {
  const chart = $("[data-season]", root);
  if (!chart || chart.dataset.bound) return;
  chart.dataset.bound = "1";
  const tip = $(".season-tip", chart);
  const show = (hit) => {
    $$(".sbar.on", chart).forEach((x) => x.classList.remove("on"));
    const bar = $(`.sbar[data-m="${hit.dataset.m}"]`, chart);
    if (bar) bar.classList.add("on");
    tip.hidden = false;
    tip.textContent = `${hit.dataset.m}月：${hit.dataset.v}回`;
    const r = (bar || hit).getBoundingClientRect(), cr = chart.getBoundingClientRect();
    tip.style.left = Math.min(Math.max(r.left + r.width / 2 - cr.left, 34), cr.width - 34) + "px";
    tip.style.top = Math.max((bar ? r.top : cr.bottom - 30) - cr.top - 6, 0) + "px";
    chart.classList.add("tipping");
  };
  $$(".shit", chart).forEach((h) => {
    h.addEventListener("pointerenter", () => show(h));
    h.addEventListener("click", () => show(h));
    h.addEventListener("focus", () => show(h));
  });
  chart.addEventListener("pointerleave", (e) => {
    if (e.pointerType !== "mouse") return;
    tip.hidden = true;
    chart.classList.remove("tipping");
    $$(".sbar.on", chart).forEach((x) => x.classList.remove("on"));
  });
}

/* ---------- 詳細：よくやる（時期・曜日・時間帯・日にち）の切り替え（決定 060） ----------
   最後に選んだものを、この端末に覚えておく。サーバーは「時期」を開いた状態で返す */
const TEND_KEY = "yl:tend-tab";
function applyTend(root, key) {
  const tabs = $$("[data-tend]", root);
  if (!tabs.some((t) => t.dataset.tend === key)) key = tabs[0].dataset.tend;
  tabs.forEach((t) => {
    const on = t.dataset.tend === key;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
  });
  $$("[data-tend-panel]", root).forEach((p) => { p.hidden = p.dataset.tendPanel !== key; });
}
export function bindTend(root) {
  const list = $(".tend-tabs", root);
  if (!list || list.dataset.bound) return;
  list.dataset.bound = "1";
  const pick = (b) => { store.set(TEND_KEY, b.dataset.tend); applyTend(root, b.dataset.tend); b.focus(); };
  list.addEventListener("click", (e) => { const b = e.target.closest("[data-tend]"); if (b) pick(b); });
  list.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const tabs = $$("[data-tend]", list), i = tabs.indexOf(document.activeElement);
    if (i < 0) return;
    e.preventDefault();
    pick(tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length]);
  });
  applyTend(root, store.get(TEND_KEY) || "season");
}
