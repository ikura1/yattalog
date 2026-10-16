// Yattalog のクライアント側。タップで記録（楽観的更新、決定 028）、長押し、タブ、編集モード、シート、トースト。
(() => {
  "use strict";
  // このページが読み込んだ、このスクリプトの URL（本番は、名前に中身のハッシュが入る）
  const BOOT_JS = (document.currentScript && document.currentScript.getAttribute("src")) || "";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* 保存できなくても動く */ } },
  };
  const TOO_MANY = "操作が多すぎます。少し待ってから、もう一度お試しください"; // 429（レート制限）
  const csrf = () => {
    const h = document.body.getAttribute("hx-headers");
    try { return JSON.parse(h)["X-CSRFToken"]; } catch (_) { return ""; }
  };
  const post = (url, data) => fetch(url, {
    method: "POST",
    headers: { "X-CSRFToken": csrf(), "X-Requested-With": "fetch" },
    body: new URLSearchParams(data),
    credentials: "same-origin",
  });

  /* ---------- 手ごたえ（記録したとき・長押しが効いたとき） ----------
     Android は振動させる。iPhone は、ブラウザから振動させる手段がないので、
     画面の外に置いたスイッチ（input[switch]）を切り替えて、OS の手ごたえを借りる（対応していない端末では何も起きない）。 */
  let hapticSwitch = null;
  function haptic(ms) {
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
  function toast(message, actions = [], opts = {}) {
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

  /* ---------- シート ---------- */
  const sheet = () => $("#sheet");
  function openSheet() {
    sheet().hidden = false;
    sheet().scrollTop = 0; // 中身が入れ替わったら、一番上から見せる（前のシートのスクロール位置を引き継がない）
    $("#scrim").hidden = false;
    // 入力欄には当てない（スマホでキーボードが開いて中身を隠すため）。読み上げのためにシート自体へ移す
    sheet().focus({ preventScroll: true });
  }
  function closeSheet() {
    if (!sheet()) return;
    sheet().hidden = true;
    $("#scrim").hidden = true;
    $("#sheet-body").innerHTML = "";
    reloadIfPending(); // シートを開いている間に見送った読み込み直しを、ここで行う
  }
  function loadSheet(url) {
    if (window.htmx) window.htmx.ajax("GET", url, { target: "#sheet-body" });
  }

  /* ---------- ホーム：タブ ---------- */
  const app = () => $("#app");
  const NO_CATEGORY_TAB = "none";
  const currentTab = () => store.get("yl:tab") || "all";
  function applyTab(tab, dir = 0) {
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
  function swipeTab(dir) {
    const ids = $$("#tabs [data-tab]").map((b) => b.dataset.tab);
    const i = ids.indexOf(currentTab()) + dir;
    if (i >= 0 && i < ids.length) applyTab(ids[i], dir);
  }

  /* ---------- ホーム：タップで記録・長押し・編集モード ---------- */
  let editing = false;
  let press = null;
  const LONG = 480, SLOP = 10, EDGE = 20;

  function setEditing(on) {
    editing = on;
    app().classList.toggle("editing", on);
    const b = $("#editBtn");
    b.textContent = on ? "完了" : "編集";
    b.setAttribute("aria-pressed", String(on));
    $("#editHint").hidden = !on;
    if (!on) reloadIfPending();
  }

  function replaceTile(li, html) {
    if (!html) return;
    const tpl = document.createElement("template");
    tpl.innerHTML = html.trim();
    const fresh = tpl.content.firstElementChild;
    fresh.hidden = li.hidden;
    li.replaceWith(fresh);
    return fresh;
  }

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

  function bindHome() {
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
      if (e.detail === 0) { editing ? (location.href = t.dataset.detailUrl) : quickRecord(t); }
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
    else quickRecord(p.el);
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
    const visible = $$("#grid > li[data-id]").filter((li) => !li.hidden);
    const i = visible.indexOf(p.drag.li);
    const before = visible[i - 1]?.dataset.id || "";
    const after = visible[i + 1]?.dataset.id || "";
    post(p.el.dataset.moveUrl, { before, after }).then((r) => {
      if (!r.ok) { toast("並べ替えを保存できませんでした"); refreshHome(); }
    }).catch(() => { toast("並べ替えを保存できませんでした"); refreshHome(); });
  }

  function refreshHome() {
    const a = app();
    if (a && a.dataset.gridUrl && window.htmx) {
      window.htmx.ajax("GET", a.dataset.gridUrl, { target: "#grid-wrap", swap: "innerHTML" });
    }
  }

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

  function bindEmojiField(root) {
    const input = $("#evEmoji", root);
    if (!input) return;
    const radios = $$('input[name="emoji"]', root);
    const sync = (e) => {
      if (e.isComposing) return; // かな漢字変換の途中は触らない
      input.value = lastGrapheme(input.value);
      if (input.value) radios.forEach((r) => { r.checked = false; });
      else if (radios.length && !radios.some((r) => r.checked)) radios[0].checked = true;
    };
    input.addEventListener("input", sync);
    input.addEventListener("compositionend", sync);
    radios.forEach((r) => r.addEventListener("change", () => { input.value = ""; }));
  }

  /* ---------- ホーム画面への追加（PWA）の案内（SPEC 3.13、決定 031・043） ----------
     閉じたら7日間は出さない。3回閉じたら、それ以降は出さない。端末ごとの話なので、ブラウザのストレージで数える。 */
  const INSTALL_KEY = "yl:install";
  const INSTALL_SNOOZE_MS = 7 * 24 * 60 * 60 * 1000;
  const INSTALL_MAX_DISMISS = 3;
  let installPrompt = null; // Android などで、ブラウザが「追加できる」と知らせてきたときの合図
  const isStandalone = () => window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  function installPlatform() {
    const ua = navigator.userAgent;
    const ios = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    if (ios) return /CriOS|FxiOS|EdgiOS|OPiOS/.test(ua) ? "ios-other" : "ios";
    return /Android/.test(ua) ? "android" : "";
  }
  function installState() {
    try { return JSON.parse(store.get(INSTALL_KEY)) || {}; } catch (_) { return {}; }
  }
  function showInstallBanner() {
    const b = $("#installBanner");
    if (!b || isStandalone()) return;
    const st = installState();
    if ((st.count || 0) >= INSTALL_MAX_DISMISS || (st.until || 0) > Date.now()) return;
    // iOS はブラウザから合図が来ないので、端末を見て出す。それ以外は、合図が来たとき（＝追加できるとき）だけ出す
    if (!installPrompt && !installPlatform().startsWith("ios")) return;
    b.hidden = false;
  }
  function openInstallGuide() {
    const a = app();
    loadSheet(`${(a && a.dataset.installUrl) || "/install/"}?p=${installPlatform()}`);
  }
  function initInstall() {
    const b = $("#installBanner");
    if (!b) return;
    $("#installYes").onclick = async () => {
      if (!installPrompt) { openInstallGuide(); return; }
      const prompt = installPrompt;
      installPrompt = null;
      prompt.prompt(); // ブラウザの追加ダイアログを開く
      try { await prompt.userChoice; } catch (_) { /* 閉じられても何もしない */ }
      b.hidden = true;
    };
    $("#installNo").onclick = () => {
      const st = installState();
      store.set(INSTALL_KEY, JSON.stringify({ count: (st.count || 0) + 1, until: Date.now() + INSTALL_SNOOZE_MS }));
      b.hidden = true;
    };
    showInstallBanner();
  }
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); installPrompt = e; showInstallBanner(); });
  window.addEventListener("appinstalled", () => { const b = $("#installBanner"); if (b) b.hidden = true; });
  document.addEventListener("click", (e) => {
    if (e.target.closest("#menuInstall")) openInstallGuide();
    if (e.target.closest("[data-close-sheet]")) closeSheet();
  });

  /* ---------- 開いたままでも経過時間を古くしない ----------
     「さっき」「N時間」「今日」は時間がたつと変わるので、画面に戻ってきたときと一定時間ごとにホームを読み直す。
     編集中・シートを開いている間・タイルを押している間・記録の送信中は、操作のじゃまになるので読み直さない。 */
  const STALE_MS = 5 * 60 * 1000;
  let gridLoadedAt = Date.now();
  function refreshIfStale() {
    if (document.hidden || !$("#grid") || !navigator.onLine) return;
    if (busy()) return;
    if (reloadPending) { reloadIfNewBuild(); return; }
    if (Date.now() - gridLoadedAt < STALE_MS) return;
    refreshHome();
  }

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
  function bindShare(root) {
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

  /* ---------- デプロイのあと、開いたままの画面を新しいスクリプトに切り替える ----------
     ホーム画面に追加したアプリは、閉じない限り、古いスクリプトを持ったまま動き続ける。
     そこへ新しい版の一覧（HTML）が届くと、動きが食い違う（例：新しく増えたタブを開いても、何も出ない）。
     一覧に付いているスクリプトの URL が、自分の読み込んだものと違っていたら、ページを読み込み直す。 */
  const RELOADED_KEY = "yl:reloaded-for";
  let reloadPending = false;
  const busy = () => editing || press || $(".pending-net") || (sheet() && !sheet().hidden);
  function reloadIfNewBuild() {
    const current = $("#grid")?.dataset.appJs;
    if (!BOOT_JS || !current || current === BOOT_JS) { reloadPending = false; return; }
    // 読み込み直しても合わないときに、繰り返さない（同じ版に向けては1回だけ）
    let done = null;
    try { done = sessionStorage.getItem(RELOADED_KEY); } catch (_) { return; }
    if (done === current) return;
    if (busy()) { reloadPending = true; return; } // 操作の途中では行わない。手が空いたら行う
    try { sessionStorage.setItem(RELOADED_KEY, current); } catch (_) { return; }
    location.reload();
  }
  const reloadIfPending = () => { if (reloadPending) reloadIfNewBuild(); };

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
  function bindRecordForm(root) {
    const form = $("#recForm", root);
    if (!form || form.dataset.bound) return;
    form.dataset.bound = "1";
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

  /* ---------- 詳細：よくやる時期のツールチップ ---------- */
  function bindSeason(root) {
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
  function bindTend(root) {
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

  /* ---------- タイムゾーン（決定 023）とオフライン表示 ---------- */
  function initTimezone() {
    const a = app();
    if (!a || !a.dataset.tzUrl) return;
    let device = "";
    try { device = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (_) { return; }
    if (!device) return;
    if (a.dataset.needsTz) {
      post(a.dataset.tzUrl, { tz: device, action: "set" }).then((r) => { if (r.ok) a.dataset.userTz = device; });
      return;
    }
    if (device === a.dataset.userTz || device === a.dataset.keptTz) return;
    const b = $("#tzBanner");
    $("#tzName").textContent = device;
    b.hidden = false;
    $("#tzYes").onclick = () => post(a.dataset.tzUrl, { tz: device, action: "set" }).then(() => { b.hidden = true; refreshHome(); toast(`タイムゾーンを ${device} にしました`); });
    $("#tzNo").onclick = () => post(a.dataset.tzUrl, { tz: device, action: "keep" }).then(() => { b.hidden = true; });
  }
  const netBanner = () => { const b = $("#netBanner"); if (b) b.hidden = navigator.onLine; };

  /* ---------- htmx との連携 ---------- */
  document.addEventListener("htmx:afterSwap", (e) => {
    const t = e.detail.target;
    if (t.id === "sheet-body") { openSheet(); bindRecordForm(t); bindEmojiField(t); bindShare(t); }
    if (t.id === "grid-wrap") { gridLoadedAt = Date.now(); bindHome(); applyTab(currentTab()); reloadIfNewBuild(); }
    if (t.id === "detail") { bindSeason(t); bindTend(t); }
  });
  // カテゴリのタブを開いているときは、追加フォームでそのカテゴリを選んでおく
  document.addEventListener("htmx:configRequest", (e) => {
    if (e.detail.elt.id !== "addTile") return;
    const tab = $('#tabs [aria-selected="true"]')?.dataset.tab;
    if (tab && tab !== "all") e.detail.parameters.category = tab; // "none" も送る。サーバーが「なし」として扱う
  });
  document.addEventListener("yl:close-sheet", closeSheet);
  document.addEventListener("yl:toast", (e) => toast(e.detail.message));
  document.addEventListener("yl:go-home", () => { if (!$("#grid")) location.href = "/"; });
  document.addEventListener("yl:changed", () => {
    if ($("#grid")) { refreshHome(); return; }
    const d = $("#detail");
    if (d && window.htmx) window.htmx.ajax("GET", location.pathname + location.search, { target: "#detail", swap: "innerHTML" });
  });
  document.addEventListener("htmx:responseError", (e) => toast(e.detail.xhr && e.detail.xhr.status === 429 ? TOO_MANY : "うまくいきませんでした。もう一度お試しください"));
  document.addEventListener("htmx:sendError", () => toast("通信できませんでした。つながっているか確認してください"));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && sheet() && !sheet().hidden) closeSheet(); });

  document.addEventListener("DOMContentLoaded", () => {
    const scrim = $("#scrim");
    if (scrim) scrim.addEventListener("click", closeSheet);
    const editBtn = $("#editBtn");
    if (editBtn) editBtn.addEventListener("click", () => setEditing(!editing));
    $("#tabs")?.closest("#grid-wrap")?.addEventListener("click", (e) => {
      const b = e.target.closest("[data-tab]");
      if (b) applyTab(b.dataset.tab);
    });
    bindHome();
    applyTab(currentTab());
    bindSeason(document);
    bindTend(document);
    initTimezone();
    initInstall();
    // オフラインのときに案内を出し、静的ファイルをしまっておく（決定 049）。失敗しても、アプリはそのまま動く
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
    netBanner();
    document.addEventListener("visibilitychange", refreshIfStale);
    setInterval(refreshIfStale, 60 * 1000);
    window.addEventListener("online", netBanner);
    window.addEventListener("offline", netBanner);
  });
})();
