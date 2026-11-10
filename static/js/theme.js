// 見た目（ライト・ダーク）の切り替え。
import { $$ } from "./dom.js";

// 設定の「見た目」は、選んだ時点で画面に当てて試せる。保存せずに閉じたら元に戻す（決定 066 の追記）
let themeBefore = null; // 試している間だけ、試す前の値（"" は「端末と同じ」）
export function applyTheme(theme) {
  if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
}
export function revertThemePreview() {
  if (themeBefore === null) return;
  applyTheme(themeBefore);
  themeBefore = null;
}
export function bindThemePreview(root) {
  $$('input[name="theme"]', root).forEach((r) => r.addEventListener("change", () => {
    if (themeBefore === null) themeBefore = document.documentElement.dataset.theme || "";
    applyTheme(r.value);
  }));
}
// 保存したら、閉じても戻さない
export function keepTheme() {
  themeBefore = null;
}
