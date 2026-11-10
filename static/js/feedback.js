// 押したときの手ごたえと、知らせ（トースト）。
import { $ } from "./dom.js";

/* ---------- 手ごたえ（記録したとき・長押しが効いたとき） ----------
   Android は振動させる。iPhone は、ブラウザから振動させる手段がないので、
   画面の外に置いたスイッチ（input[switch]）を切り替えて、OS の手ごたえを借りる（対応していない端末では何も起きない）。 */
let hapticSwitch = null;
export function haptic(ms) {
  if (document.body.dataset.haptics === "0") return; // 設定でオフ（決定 066）
  try {
    if (navigator.vibrate) { navigator.vibrate(ms); return; }
    if (!hapticSwitch) {
      hapticSwitch = document.createElement("label");
      hapticSwitch.className = "haptic";
      hapticSwitch.setAttribute("aria-hidden", "true");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.setAttribute("switch", "");
      input.tabIndex = -1;
      hapticSwitch.appendChild(input);
      document.body.appendChild(hapticSwitch);
    }
    hapticSwitch.click();
  } catch (_) { /* 手ごたえは、なくても困らない */ }
}

/* ---------- トースト（触っている間は消さない、レビュー D3） ---------- */
export function toast(message, actions = [], opts = {}) {
  const root = $("#toast-root");
  if (!root) return;
  root.querySelectorAll(".toast:not(.hint)").forEach((n) => n.remove());
  const el = document.createElement("div");
  el.className = "toast" + (opts.hint ? " hint" : "") + (opts.stack ? " stack" : "");
  el.setAttribute("role", "status");
  const p = document.createElement("p");
  p.textContent = message;
  el.appendChild(p);
  actions.forEach((a) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = a.label;
    b.addEventListener("click", () => { el.remove(); a.fn(); });
    el.appendChild(b);
  });
  const dur = opts.duration || (actions.length ? 5000 : 2200);
  if (actions.length) {
    const m = document.createElement("span");
    m.className = "meter";
    m.style.setProperty("--dur", dur + "ms");
    el.appendChild(m);
  }
  root.appendChild(el);
  let left = dur, started = Date.now(), timer = null;
  const run = () => { started = Date.now(); timer = setTimeout(() => el.remove(), left); };
  const hold = () => { clearTimeout(timer); left -= Date.now() - started; el.classList.add("hold"); };
  const resume = () => { el.classList.remove("hold"); run(); };
  el.addEventListener("pointerenter", hold);
  el.addEventListener("pointerleave", resume);
  el.addEventListener("focusin", hold);
  el.addEventListener("focusout", resume);
  run();
}
