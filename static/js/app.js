// Yattalog のクライアント側。タップで記録（楽観的更新、決定 028）、長押し、タブ、編集モード、シート、トースト。
(() => {
  "use strict";
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

  /* ---------- トースト（触っている間は消さない、レビュー D3） ---------- */
  function toast(message, actions = [], opts = {}) {
    const root = $("#toast-root");
    if (!root) return;
    root.querySelectorAll(".toast:not(.hint)").forEach((n) => n.remove());
    const el = document.createElement("div");
    el.className = "toast" + (opts.hint ? " hint" : "");
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
    $("#scrim").hidden = false;
    // 入力欄には当てない（スマホでキーボードが開いて中身を隠すため）。読み上げのためにシート自体へ移す
    sheet().focus({ preventScroll: true });
  }
  function closeSheet() {
    if (!sheet()) return;
    sheet().hidden = true;
    $("#scrim").hidden = true;
    $("#sheet-body").innerHTML = "";
  }
  function loadSheet(url) {
    if (window.htmx) window.htmx.ajax("GET", url, { target: "#sheet-body" });
  }

  /* ---------- ホーム：タブ ---------- */
  const app = () => $("#app");
  const currentTab = () => store.get("yl:tab") || "all";
  function applyTab(tab, dir = 0) {
    const tabs = $("#tabs");
    if (!tabs) return;
    if (!$(`[data-tab="${CSS.escape(tab)}"]`, tabs)) tab = "all";
    store.set("yl:tab", tab);
    $$("[data-tab]", tabs).forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
    let shown = 0;
    $$("#grid > li[data-id]").forEach((li) => {
      const on = tab === "all" || li.dataset.category === tab;
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
    try {
      const res = await post(btn.dataset.recordUrl, { log_id: logId });
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      const fresh = replaceTile(li, data.tile_html);
      const fbtn = fresh && $(".tile", fresh);
      if (data.streak_grew && fbtn) { const s = $(".streak", fbtn); if (s) s.classList.add("burst"); }
      const name = $(".name", fbtn || btn)?.textContent || "";
      toast(data.streak_grew ? `🔥 ${data.streak_text}！` : `やった！ ${name} を記録しました`, [
        { label: "取り消す", fn: () => undo(data.log_id, fresh) },
        { label: "メモを足す", fn: () => loadSheet(`/logs/${data.log_id}/edit/`) },
      ]);
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
          if (navigator.vibrate) { try { navigator.vibrate(15); } catch (_) { /* 非対応 */ } }
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

  /* ---------- 開いたままでも経過時間を古くしない ----------
     「さっき」「N時間」「今日」は時間がたつと変わるので、画面に戻ってきたときと一定時間ごとにホームを読み直す。
     編集中・シートを開いている間・タイルを押している間・記録の送信中は、操作のじゃまになるので読み直さない。 */
  const STALE_MS = 5 * 60 * 1000;
  let gridLoadedAt = Date.now();
  function refreshIfStale() {
    if (document.hidden || !$("#grid") || !navigator.onLine) return;
    if (editing || press || $(".pending-net") || (sheet() && !sheet().hidden)) return;
    if (Date.now() - gridLoadedAt < STALE_MS) return;
    refreshHome();
  }

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
    if (t.id === "sheet-body") { openSheet(); bindRecordForm(t); bindEmojiField(t); }
    if (t.id === "grid-wrap") { gridLoadedAt = Date.now(); bindHome(); applyTab(currentTab()); }
    if (t.id === "detail") bindSeason(t);
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
    initTimezone();
    netBanner();
    document.addEventListener("visibilitychange", refreshIfStale);
    setInterval(refreshIfStale, 60 * 1000);
    window.addEventListener("online", netBanner);
    window.addEventListener("offline", netBanner);
  });
})();
