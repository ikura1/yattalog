// デプロイのあと、開いたままの画面を新しいスクリプトに切り替える。
import { $ } from "./dom.js";

/* ホーム画面に追加したアプリは、閉じない限り、古いスクリプトを持ったまま動き続ける。
   そこへ新しい版の一覧（HTML）が届くと、動きが食い違う（例：新しく増えたタブを開いても、何も出ない）。
   一覧に付いている入口のスクリプトの URL が、自分の読み込んだものと違っていたら、ページを読み込み直す。
   本番では、どのファイルを変えても入口の名前（中身のハッシュ）が変わる（決定 070）。 */
const RELOADED_KEY = "yl:reloaded-for";
let bootJs = ""; // このページが読み込んだ、入口のスクリプトの URL
let reloadPending = false;
export function setBootScript(url) {
  bootJs = url;
}

// 操作の途中（編集中・シートを開いている間・記録の送信中など）かどうか。それぞれの機能が、確かめ方を足す
const busyChecks = [];
export function whenBusy(check) {
  busyChecks.push(check);
}
export const busy = () => busyChecks.some((check) => check());

export function reloadIfNewBuild() {
  const current = $("#grid")?.dataset.appJs;
  if (!bootJs || !current || new URL(current, location.href).href === bootJs) { reloadPending = false; return; }
  // 読み込み直しても合わないときに、繰り返さない（同じ版に向けては1回だけ）
  let done = null;
  try { done = sessionStorage.getItem(RELOADED_KEY); } catch (_) { return; }
  if (done === current) return;
  if (busy()) { reloadPending = true; return; } // 操作の途中では行わない。手が空いたら行う
  try { sessionStorage.setItem(RELOADED_KEY, current); } catch (_) { return; }
  location.reload();
}
export const isReloadPending = () => reloadPending;
export const reloadIfPending = () => { if (reloadPending) reloadIfNewBuild(); };
