// 絵文字の入力欄と、名前から出すアイコンの候補。
import { $, $$ } from "./dom.js";

/* ---------- アイコン：おすすめの一覧か、入力欄のどちらか一方（決定 035） ----------
   入力欄には絵文字を1つだけ残す（続けて打ったら、最後の1つに置き換える）。正しいかどうかはサーバーで確かめる。 */
function lastGrapheme(text) {
  const s = text.trim();
  if (!s || !window.Intl || !Intl.Segmenter) return s;
  const parts = [...new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(s)];
  return parts[parts.length - 1].segment;
}
// 絵文字を1つだけ入れる欄（カテゴリの絵文字など）。続けて打ったら、最後の1つに置き換える
const keepOneEmoji = (e) => {
  const el = e.target;
  if (e.isComposing || !el.matches || !el.matches("[data-one-emoji]")) return;
  const one = lastGrapheme(el.value);
  if (el.value !== one) el.value = one;
};
document.addEventListener("input", keepOneEmoji);
document.addEventListener("compositionend", keepOneEmoji);

export function bindEmojiField(root) {
  const input = $("#evEmoji", root);
  if (!input) return;
  // 候補の行は名前を打つたびに作り直すので、その都度さがす
  const radios = () => $$('input[name="emoji"]', root);
  const sync = (e) => {
    if (e.isComposing) return; // かな漢字変換の途中は触らない
    input.value = lastGrapheme(input.value);
    if (input.value) radios().forEach((r) => { r.checked = false; });
    else if (radios().length && !radios().some((r) => r.checked)) radios()[0].checked = true;
  };
  input.addEventListener("input", sync);
  input.addEventListener("compositionend", sync);
  root.addEventListener("change", (e) => { if (e.target.name === "emoji") input.value = ""; });
  bindEmojiHints(root);
}

/* ---------- 名前からアイコンの候補を出す（決定 065） ----------
   辞書はサーバーと同じもの（data-emoji-hints）。新しく作るときだけ、名前を打つたびに候補を出し直し、先頭を選んでおく。
   自分で選んだら（候補・一覧・入力欄のどれでも）、そのあとは変えない */
// 比べる前にそろえる：全角・半角（NFKC）、大文字・小文字、カタカナ → ひらがな（サーバーの normalize() と同じ）
const normalizeHint = (s) => s.normalize("NFKC").toLowerCase()
  .replace(/[\u30a1-\u30f6]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60));
// 当たった言葉が長い組ほど先。同じ長さなら名前の先に出てくる言葉の組、それも同じなら辞書の上の組（サーバーの suggest() と同じ）
function suggestEmojis(name, data) {
  const text = normalizeHint(name);
  const ranked = [];
  data.hints.forEach(([words, emojis], order) => {
    let best = null;
    words.forEach((w) => {
      const nw = normalizeHint(w), at = text.indexOf(nw);
      if (at >= 0 && (!best || nw.length > best.len || (nw.length === best.len && at < best.at))) best = { len: nw.length, at };
    });
    if (best) ranked.push({ ...best, order, emojis });
  });
  ranked.sort((a, b) => b.len - a.len || a.at - b.at || a.order - b.order);
  const found = [];
  ranked.forEach(({ emojis }) => emojis.forEach((e) => { if (!found.includes(e)) found.push(e); }));
  return found.length ? found.slice(0, data.limit) : data.fallback.slice();
}
function bindEmojiHints(root) {
  const field = $(".emoji-field", root);
  const name = $("#evName", root);
  if (!field || !name || field.dataset.auto !== "1") return;
  let data;
  try { data = JSON.parse(field.dataset.emojiHints); } catch (_) { return; }
  const row = $(".emo-row", field), why = $(".emo-why", field), custom = $("#evEmoji", root);
  let byHand = false;
  field.addEventListener("change", (e) => { if (e.isTrusted && e.target.name === "emoji") byHand = true; });
  if (custom) custom.addEventListener("input", () => { if (custom.value) byHand = true; });
  // カテゴリの絵文字は付けなくてもよい（data-optional）。先頭に「なし」を置いて選んでおき、候補は並べるだけにする
  const optional = field.dataset.optional === "1";
  const option = (value, label, checked) => {
    const el = document.createElement("label");
    el.className = "emo-opt" + (value ? "" : " emo-none");
    const r = document.createElement("input");
    r.type = "radio"; r.name = "emoji"; r.value = value; r.checked = checked;
    const span = document.createElement("span");
    span.textContent = label;
    el.append(r, span);
    return el;
  };
  const refresh = () => {
    if (byHand) return;
    const text = name.value.trim();
    const list = suggestEmojis(text, data);
    const opts = list.map((e, i) => option(e, e, !optional && i === 0));
    row.replaceChildren(...(optional ? [option("", "なし", true), ...opts.slice(0, data.limit - 1)] : opts));
    if (custom) custom.value = "";
    const none = list.join() === data.fallback.join();
    if (optional) why.textContent = text && !none ? "合いそうな絵文字です。押すと付けられます" : "タブで、名前の前に出ます";
    else why.textContent = !text ? "名前を入れると、合いそうな絵文字を選んでおきます"
      : none ? "合う候補が見つからなかったので、よく使うものを出しています"
      : `「${text}」に合いそうなものを選んでおきました`;
  };
  name.addEventListener("input", refresh);
}
