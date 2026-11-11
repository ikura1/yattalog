// カテゴリの管理シート。
import { $, $$, drain, post } from "./dom.js";
import { toast } from "./feedback.js";

// カテゴリの並べ替え（シートの中）。取っ手（≡）を押したまま上下に動かすか、取っ手で ↑↓ キー。
// 動かしたら、前後のカテゴリをサーバーに送り、ホームのタブも並べ直す
export function bindCategorySort(root) {
  const list = $(".catlist[data-move-url]", root);
  if (!list || list.dataset.bound) return;
  list.dataset.bound = "1";
  const items = () => $$(":scope > li[data-id]", list);
  const save = (li) => {
    const all = items(), i = all.indexOf(li);
    const data = { action: "move", id: li.dataset.id, before: all[i - 1]?.dataset.id || "", after: all[i + 1]?.dataset.id || "" };
    post(list.dataset.moveUrl, data).then(drain).then((r) => {
      if (!r.ok) throw new Error(String(r.status));
      document.dispatchEvent(new CustomEvent("yl:changed"));
    }).catch(() => {
      toast("並べ替えを保存できませんでした");
      if (window.htmx) window.htmx.ajax("GET", list.dataset.moveUrl, { target: "#sheet-body", swap: "innerHTML" });
    });
  };
  let drag = null;
  list.addEventListener("pointerdown", (e) => {
    const handle = e.target.closest(".cat-handle");
    if (!handle) return;
    e.preventDefault();
    window.getSelection()?.removeAllRanges(); // すでに選ばれている文字があれば外す
    drag = { li: handle.closest("li"), moved: false };
    drag.li.classList.add("dragging");
    document.body.classList.add("sorting"); // ドラッグのあいだ、画面のどこでも文字を選ばせない
    try { handle.setPointerCapture(e.pointerId); } catch (_) { /* 捕まえられなくても、一覧の中なら動く */ }
  });
  list.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const over = items().find((li) => {
      if (li === drag.li) return false;
      const r = li.getBoundingClientRect();
      return e.clientY > r.top && e.clientY < r.bottom;
    });
    if (!over) return;
    const r = over.getBoundingClientRect();
    list.insertBefore(drag.li, e.clientY > r.top + r.height / 2 ? over.nextSibling : over);
    drag.moved = true;
  });
  const end = () => {
    if (!drag) return;
    drag.li.classList.remove("dragging");
    document.body.classList.remove("sorting");
    if (drag.moved) save(drag.li);
    drag = null;
  };
  list.addEventListener("pointerup", end);
  list.addEventListener("pointercancel", end);
  // 指が一覧の外で離れても、ドラッグを終える
  document.addEventListener("pointerup", end);
  document.addEventListener("selectstart", (e) => { if (drag) e.preventDefault(); });
  list.addEventListener("keydown", (e) => {
    const handle = e.target.closest(".cat-handle");
    if (!handle || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
    e.preventDefault();
    const li = handle.closest("li");
    const up = e.key === "ArrowUp";
    const sib = up ? li.previousElementSibling : li.nextElementSibling;
    if (!sib || !sib.dataset.id) return;
    list.insertBefore(li, up ? sib : sib.nextSibling);
    handle.focus();
    save(li);
  });
}
