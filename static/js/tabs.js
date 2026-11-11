// ホームのタブ（カテゴリ）。最後に開いたタブは、端末に覚える。
import { $, $$, store } from "./dom.js";

/* ---------- ホーム：タブ ---------- */

const NO_CATEGORY_TAB = "none";
export const currentTab = () => store.get("yl:tab") || "all";
export function applyTab(tab, dir = 0) {
  const tabs = $("#tabs");
  if (!tabs) return;
  if (!$(`[data-tab="${CSS.escape(tab)}"]`, tabs)) tab = "all";
  store.set("yl:tab", tab);
  $$("[data-tab]", tabs).forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
  let shown = 0;
  $$("#grid > li[data-id]").forEach((li) => {
    // "none" は「カテゴリなし」のタブ。カテゴリに入っていないイベントだけを出す（決定 050）
    const on = tab === "all" || li.dataset.category === (tab === NO_CATEGORY_TAB ? "" : tab);
    li.hidden = !on;
    if (on) shown++;
  });
  $("#tabEmpty").hidden = !(tab !== "all" && shown === 0);
  const sel = $('[aria-selected="true"]', tabs);
  if (sel) sel.scrollIntoView({ block: "nearest", inline: "nearest" });
  if (dir) {
    const g = $("#grid");
    g.classList.remove("slide-l", "slide-r");
    void g.offsetWidth;
    g.classList.add(dir > 0 ? "slide-l" : "slide-r");
  }
}
export function swipeTab(dir) {
  const ids = $$("#tabs [data-tab]").map((b) => b.dataset.tab);
  const i = ids.indexOf(currentTab()) + dir;
  if (i >= 0 && i < ids.length) applyTab(ids[i], dir);
}
