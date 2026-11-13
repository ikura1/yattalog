// 記録シートの日付の選び方。
import { $, $$ } from "./dom.js";

/* ---------- 記録シート：「今／昨日／一昨日／日付を選ぶ」 ----------
   日付の計算はサーバーで行い、今日・昨日・一昨日の日付は data 属性で受け取る（レビュー 10）。
   JS は「どれが選ばれているか」と、表示用の文字列を組み立てるだけ。 */
function dayLabel(iso, f) {
  if (iso === f.dataset.today) return "今日";
  if (iso === f.dataset.yesterday) return "昨日";
  if (iso === f.dataset.dayBefore) return "一昨日";
  const [, m, d] = iso.split("-").map(Number);
  return `${m}月${d}日`;
}
function modeFor(iso, f) {
  if (iso === f.dataset.yesterday) return "y1";
  if (iso === f.dataset.dayBefore) return "y2";
  return "pick";
}
export function bindRecordForm(root) {
  const form = $("#recForm", root);
  if (!form || form.dataset.bound) return;
  form.dataset.bound = "1";
  // 入れてある前回の数字は、触ったら丸ごと選ぶ（打てばそのまま置き換わる）
  $('input[name="value"]', form)?.addEventListener("focus", (e) => e.target.select());
  const seg = $("[data-when-seg]", form), hidden = $('input[name="when"]', form);
  const box = $("[data-pickbox]", form), dI = $('input[name="date"]', form), tI = $('input[name="time"]', form);
  const note = $("[data-when-note]", form);
  let mode = seg.dataset.initial === "pick" ? modeFor(dI.value, form) : seg.dataset.initial;
  const sync = () => {
    $$("[data-w]", seg).forEach((b) => b.setAttribute("aria-checked", String(b.dataset.w === mode)));
    hidden.value = mode === "now" ? "now" : "pick";
    box.hidden = mode === "now";
    note.textContent = mode === "now" ? "今の時刻で記録します"
      : `${dayLabel(dI.value || form.dataset.today, form)}${tI.value ? " " + tI.value : "（時刻なし）"} として記録します`;
  };
  seg.addEventListener("click", (e) => {
    const b = e.target.closest("[data-w]");
    if (!b) return;
    mode = b.dataset.w;
    if (mode === "y1") dI.value = form.dataset.yesterday;
    if (mode === "y2") dI.value = form.dataset.dayBefore;
    if (mode === "pick" && !dI.value) dI.value = form.dataset.today;
    sync();
  });
  dI.addEventListener("input", () => { mode = modeFor(dI.value, form); sync(); });
  tI.addEventListener("input", sync);
  sync();
}
