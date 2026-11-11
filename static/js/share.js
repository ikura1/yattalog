// シェアの画像を、端末で作る。
import { $, post } from "./dom.js";
import { toast } from "./feedback.js";

/* ---------- シェア（SPEC 3.8、決定 017・053） ----------
   画像（1080×1350、常にライト配色）は、端末の Canvas で作る。サーバーには送らない。
   スマホでは共有シートに渡し、渡せない環境では、画像を保存できるようにする。 */
const SHARE_TINT = {
  tomato: "#FFD9D2", tangerine: "#FFE3C2", sun: "#FFF1B8", leaf: "#D7F0C8",
  teal: "#C9EEE6", sky: "#D3E6FF", grape: "#E4DAFF", pink: "#FFDCEB",
};
const SHARE_DISPLAY = '"M PLUS Rounded 1c", "Hiragino Maru Gothic ProN", sans-serif';
const SHARE_BODY = '"Zen Kaku Gothic New", "Hiragino Sans", sans-serif';
function wrapText(ctx, text, maxWidth) {
  const lines = [];
  let line = "";
  for (const ch of text) {
    if (ctx.measureText(line + ch).width > maxWidth && line) { lines.push(line); line = ch; } else line += ch;
  }
  if (line) lines.push(line);
  return lines;
}
function roundedRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(x, y, w, h, r); else ctx.rect(x, y, w, h);
  ctx.fill();
}
async function drawShareCard(d, withMemo) {
  // 文字の形が決まってから描く（読み込み前に描くと、別の書体になる）
  try { await Promise.all([document.fonts.load(`800 76px ${SHARE_DISPLAY}`), document.fonts.load(`500 44px ${SHARE_BODY}`)]); } catch (_) { /* 代わりの書体で描く */ }
  const W = 1080, H = 1350;
  const canvas = document.createElement("canvas");
  canvas.width = W; canvas.height = H;
  const x = canvas.getContext("2d");
  const tint = SHARE_TINT[d.color] || "#EEF1F6";
  const ink = "#1B2333", sub = "#4A5568", accent = "#1F6F5C";
  x.fillStyle = tint; x.fillRect(0, 0, W, H);
  const cx = 72, cy = 72, cw = W - 144, ch = H - 144;
  x.fillStyle = "#FFFFFF"; roundedRect(x, cx, cy, cw, ch, 56);
  x.textAlign = "center"; x.textBaseline = "alphabetic";
  const memo = withMemo && d.memo ? d.memo.replace(/\s+/g, " ") : "";
  const note = d.sub || ""; // 連続記録のときの「通算 24回目」。古い HTML には無いので、空として扱う
  let y = (memo ? 380 : 450) - (note ? 35 : 0);
  x.fillStyle = ink; x.font = `220px ${SHARE_DISPLAY}`; x.fillText(d.emoji, W / 2, y);
  x.font = `800 76px ${SHARE_DISPLAY}`;
  y += 130;
  wrapText(x, d.name, cw - 140).slice(0, 2).forEach((line) => { x.fillText(line, W / 2, y); y += 92; });
  x.fillStyle = accent; x.font = `800 120px ${SHARE_DISPLAY}`; x.fillText("やった！", W / 2, y + 70); y += 130;
  x.font = `800 64px ${SHARE_DISPLAY}`;
  const pill = x.measureText(d.headline).width + 90;
  x.fillStyle = tint; roundedRect(x, W / 2 - pill / 2, y + 10, pill, 104, 52);
  x.fillStyle = ink; x.fillText(d.headline, W / 2, y + 85); y += 150;
  if (note) { x.fillStyle = sub; x.font = `800 46px ${SHARE_DISPLAY}`; x.fillText(note, W / 2, y + 30); y += 70; }
  if (memo) {
    x.fillStyle = sub; x.font = `500 44px ${SHARE_BODY}`;
    wrapText(x, memo, cw - 200).slice(0, 2).forEach((line) => { x.fillText(line, W / 2, y + 40); y += 62; });
  }
  x.fillStyle = sub; x.font = `500 40px ${SHARE_BODY}`; x.fillText(d.when, W / 2, cy + ch - 120);
  x.font = `800 44px ${SHARE_DISPLAY}`;
  const w1 = x.measureText("Yatta").width, w2 = x.measureText("log").width;
  x.textAlign = "left";
  x.fillStyle = ink; x.fillText("Yatta", W / 2 - (w1 + w2) / 2, cy + ch - 50);
  x.fillStyle = accent; x.fillText("log", W / 2 - (w1 + w2) / 2 + w1, cy + ch - 50);
  return canvas;
}
export function bindShare(root) {
  const card = $("#shareCard", root);
  if (!card) return;
  const d = card.dataset;
  const img = $("#shareImg", root), memo = $("#shareMemo", root), note = $("#shareNote", root), save = $("#shareSave", root);
  let blob = null, url = null;
  const redraw = async () => {
    const canvas = await drawShareCard(d, memo.checked);
    blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    if (url) URL.revokeObjectURL(url);
    url = URL.createObjectURL(blob);
    img.src = url;
    save.href = url;
  };
  // シェアした、とサーバーに知らせる（実績「シェアデビュー」、決定 063）。シェアそのものは端末で完結する
  const shared = () => {
    if (!d.sharedUrl) return;
    post(d.sharedUrl, {}).then((r) => (r.ok ? r.json() : {})).then((j) => { if (j.achievement) toast(j.achievement); }).catch(() => {});
  };
  save.addEventListener("click", shared);
  memo.addEventListener("change", redraw);
  $("#shareDo", root).addEventListener("click", async () => {
    if (!blob) return;
    const file = new File([blob], "yattalog.png", { type: "image/png" });
    try {
      if (!navigator.canShare || !navigator.canShare({ files: [file] })) throw new Error("unsupported");
      await navigator.share({ files: [file], text: d.text });
      shared();
    } catch (err) {
      if (err && err.name === "AbortError") return; // 共有シートを閉じただけ
      note.textContent = "この環境では、共有シートに画像を渡せませんでした。「画像を保存する」で保存して、投稿に添えてください";
      note.hidden = false;
      save.hidden = false;
    }
  });
  redraw();
}
