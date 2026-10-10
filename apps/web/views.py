"""画面（Django テンプレート＋htmx）。処理はすべてサービス層に任せる（決定 027）。"""

import calendar
import json
import uuid
from datetime import date, time

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.events.models import COLORS, Category, Event, Log, StreakUnit
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services import stats
from apps.events.services.dates import today_in, zone
from apps.events.services.logs import When
from apps.events.services.streaks import STREAK_MIN
from apps.spaces.services import personal_space
from apps.web.presenters import tile

EMOJIS = [
    "🛏️",
    "✂️",
    "🌀",
    "🚲",
    "🧗",
    "🦷",
    "🚗",
    "🪴",
    "📞",
    "🏋️",
    "🧺",
    "🧹",
    "🍳",
    "💊",
    "🐈",
    "🛁",
    "🧴",
    "🔋",
    "📚",
    "🎸",
    "🏃",
    "💇",
    "🧽",
    "🗑️",
]
UNITS = [(u.value, u.label) for u in StreakUnit]


# --- 共通 ----------------------------------------------------------------------


def _today(request: HttpRequest) -> date:
    return today_in(request.user.timezone)


def _event(request: HttpRequest, event_id) -> Event:
    try:
        return Event.objects.select_related("category").get(id=event_id, space__members__user=request.user)
    except Event.DoesNotExist, ValueError, ValidationError:
        raise Http404 from None


def _log(request: HttpRequest, log_id) -> Log:
    try:
        return log_svc.get_log_for(request.user, log_id)
    except Log.DoesNotExist:
        raise Http404 from None


def _categories(request: HttpRequest):
    return Category.objects.filter(space__members__user=request.user).order_by("sort_key")


def _refresh(resp: HttpResponse, toast: str | None = None, **extra) -> HttpResponse:
    """htmx に「ホーム（や詳細）を更新して、シートを閉じて」と伝える。"""
    trig: dict = {
        "yl:changed": True,
        "yl:close-sheet": True,
        **{f"yl:{k.replace('_', '-')}": v for k, v in extra.items()},
    }
    if toast:
        trig["yl:toast"] = {"message": toast}
    resp["HX-Trigger"] = json.dumps(trig)  # ASCII のみ（ヘッダーに日本語をそのまま入れない）
    return resp


def _form_error(request, template, ctx, err: ValidationError) -> HttpResponse:
    ctx["error"] = " ".join(err.messages)
    resp = render(request, template, ctx)
    resp["HX-Retarget"] = "#sheet-body"
    resp["HX-Reswap"] = "innerHTML"
    return resp


def _parse_when(post) -> When:
    mode = post.get("when", "now")
    if mode == "now":
        return When()
    try:
        d = date.fromisoformat(post.get("date", ""))
    except ValueError:
        raise ValidationError("日付を選んでください") from None
    t_raw = (post.get("time") or "").strip()
    t = time.fromisoformat(t_raw) if t_raw else None
    return When(date=d, time=t)


# --- ログイン・ホーム -------------------------------------------------------------


@require_GET
def login_page(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("web:home")
    return render(request, "web/login.html")


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    resp = redirect("web:login")
    resp["Clear-Site-Data"] = '"cache", "storage"'  # 共用端末で前の人のデータが残らないように（レビュー E9）
    return resp


@login_required
@require_GET
def home(request: HttpRequest) -> HttpResponse:
    return render(request, "web/home.html", _home_ctx(request))


def _home_ctx(request: HttpRequest) -> dict:
    space = personal_space(request.user)
    today = _today(request)
    events = Event.objects.filter(space=space, is_archived=False).select_related("category").order_by("sort_key")
    cats = list(_categories(request))
    counts = {c.id: 0 for c in cats}
    for e in events:
        if e.category_id in counts:
            counts[e.category_id] += 1
    return {
        "tiles": [tile(e, today) for e in events],
        "categories": [(c, counts[c.id]) for c in cats],
        "total": len(events),
        "user_tz": request.user.timezone,
        "needs_tz": request.user.onboarded_at is None,
    }


@login_required
@require_GET
def grid(request: HttpRequest) -> HttpResponse:
    """ホームのグリッドとタブだけを返す（htmx で差し替える）。"""
    return render(request, "web/_grid.html", _home_ctx(request))


@login_required
@require_POST
def set_timezone(request: HttpRequest) -> HttpResponse:
    """端末のタイムゾーンを設定する。初回はそのまま設定し、以降は「切り替える／このまま」の結果を受ける（決定 023）。"""
    tz = request.POST.get("tz", "")
    action = request.POST.get("action", "set")
    user = request.user
    try:
        zone(tz)
        from zoneinfo import ZoneInfo

        ZoneInfo(tz)
    except Exception:
        return HttpResponse(status=400)
    if action == "keep":
        user.timezone_kept_for = tz
    else:
        user.timezone = tz
    if user.onboarded_at is None:
        user.onboarded_at = timezone.now()
    user.save(update_fields=["timezone", "timezone_kept_for", "onboarded_at"])
    return JsonResponse({"timezone": user.timezone})


# --- 記録（タップ・取り消し）。端末で作った ID を受け取る（決定 028） ---------------------------


def _tile_html(request, event) -> str:
    event.refresh_from_db()
    return render_to_string("web/_tile.html", {"t": tile(event, _today(request))}, request=request)


@login_required
@require_POST
def record(request: HttpRequest, event_id) -> JsonResponse:
    try:
        log_id = uuid.UUID(request.POST.get("log_id", ""))
    except ValueError:
        return JsonResponse({"error": "記録 ID が正しくありません"}, status=400)
    try:
        result = log_svc.record(request.user, event_id, log_id, _parse_when(request.POST), request.POST.get("memo", ""))
    except Event.DoesNotExist:
        raise Http404 from None
    except PermissionDenied:
        return JsonResponse({"error": "この記録はできません"}, status=409)
    except ValidationError as e:
        return JsonResponse({"error": " ".join(e.messages)}, status=422)
    event = result.log.event
    grew = result.streak_after > result.streak_before and result.streak_after >= STREAK_MIN
    t = tile(Event.objects.get(id=event.id), _today(request))
    return JsonResponse(
        {
            "log_id": str(result.log.id),
            "created": result.created,
            "tile_html": _tile_html(request, event),
            "streak_grew": grew,
            "streak_text": t.streak.text if t.streak else "",
        }
    )


@login_required
@require_POST
def undo(request: HttpRequest, log_id) -> JsonResponse:
    event = log_svc.undo(request.user, log_id)
    if event is None:
        return JsonResponse({"tile_html": None})
    return JsonResponse({"tile_html": _tile_html(request, event)})


# --- 長押しシート（詳しく記録） ---------------------------------------------------------


@login_required
def record_sheet(request: HttpRequest, event_id) -> HttpResponse:
    event = _event(request, event_id)
    today = _today(request)
    ctx = {
        "event": event,
        "today": today,
        "preset": request.GET.get("date", ""),
        "log": None,
        "new_log_id": uuid.uuid7(),
    }
    if request.method == "POST":
        try:
            log_id = uuid.UUID(request.POST["log_id"])
            log_svc.record(request.user, event.id, log_id, _parse_when(request.POST), request.POST.get("memo", ""))
        except (ValidationError, ValueError, KeyError) as e:
            err = e if isinstance(e, ValidationError) else ValidationError("入力を確認してください")
            ctx["form"] = request.POST
            return _form_error(request, "web/_record_sheet.html", ctx, err)
        return _refresh(HttpResponse(status=204), "やった！ 記録しました")
    return render(request, "web/_record_sheet.html", ctx)


@login_required
def log_edit_sheet(request: HttpRequest, log_id) -> HttpResponse:
    log = _log(request, log_id)
    ctx = {"event": log.event, "today": _today(request), "log": log, "preset": ""}
    if request.method == "POST":
        try:
            log_svc.edit(request.user, log.id, _parse_when(request.POST), request.POST.get("memo", ""))
        except (ValidationError, ValueError) as e:
            err = e if isinstance(e, ValidationError) else ValidationError("入力を確認してください")
            ctx["form"] = request.POST
            return _form_error(request, "web/_record_sheet.html", ctx, err)
        return _refresh(HttpResponse(status=204), "記録を更新しました")
    return render(request, "web/_record_sheet.html", ctx)


@login_required
@require_POST
def log_delete(request: HttpRequest, log_id) -> HttpResponse:
    log_svc.undo(request.user, log_id)
    return _refresh(HttpResponse(status=204), "記録を削除しました")


# --- イベントの追加・編集・削除・並べ替え -------------------------------------------------


def _event_form_ctx(request, event=None, **extra) -> dict:
    tab = request.GET.get("category") or request.POST.get("category") or ""
    return {
        "event": event,
        "emojis": EMOJIS,
        "colors": COLORS,
        "units": UNITS,
        "categories": _categories(request),
        "selected_category": str(event.category_id) if event and event.category_id else tab,
        "today": _today(request),
        **extra,
    }


@login_required
def event_new(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        p = request.POST
        try:
            last = date.fromisoformat(p["last_done"]) if p.get("last_done") else None
            ev_svc.create_event(
                request.user,
                name=p.get("name", ""),
                emoji=p.get("emoji", ""),
                color=p.get("color", ""),
                streak_unit=p.get("streak_unit", StreakUnit.DAY),
                category_id=p.get("category") or None,
                last_done=last,
            )
        except (ValidationError, ValueError) as e:
            err = e if isinstance(e, ValidationError) else ValidationError("入力を確認してください")
            return _form_error(request, "web/_event_sheet.html", _event_form_ctx(request, form=p), err)
        return _refresh(HttpResponse(status=204), "追加しました")
    return render(request, "web/_event_sheet.html", _event_form_ctx(request))


@login_required
def event_edit(request: HttpRequest, event_id) -> HttpResponse:
    event = _event(request, event_id)
    if request.method == "POST":
        p = request.POST
        try:
            ev_svc.update_event(
                request.user,
                event.id,
                name=p.get("name", ""),
                emoji=p.get("emoji", ""),
                color=p.get("color", ""),
                streak_unit=p.get("streak_unit", StreakUnit.DAY),
                category_id=p.get("category") or None,
            )
        except ValidationError as e:
            return _form_error(request, "web/_event_sheet.html", _event_form_ctx(request, event, form=p), e)
        return _refresh(HttpResponse(status=204), "保存しました")
    return render(request, "web/_event_sheet.html", _event_form_ctx(request, event))


@login_required
def event_remove(request: HttpRequest, event_id) -> HttpResponse:
    event = _event(request, event_id)
    if request.method == "POST":
        if request.POST.get("action") == "delete":
            ev_svc.delete_event(request.user, event.id)
            return _refresh(HttpResponse(status=204), "削除しました", go_home=True)
        ev_svc.set_archived(request.user, event.id, True)
        return _refresh(HttpResponse(status=204), "アーカイブしました", go_home=True)
    return render(request, "web/_remove_sheet.html", {"event": event})


@login_required
@require_POST
def event_restore(request: HttpRequest, event_id) -> HttpResponse:
    ev_svc.set_archived(request.user, event_id, False)
    return _refresh(HttpResponse(status=204), "ホームに戻しました")


@login_required
@require_POST
def event_move(request: HttpRequest, event_id) -> HttpResponse:
    try:
        ev_svc.move_event(
            request.user,
            event_id,
            before_id=request.POST.get("before") or None,
            after_id=request.POST.get("after") or None,
        )
    except Event.DoesNotExist:
        raise Http404 from None
    except ValidationError:
        return HttpResponse(status=422)
    return HttpResponse(status=204)


# --- カテゴリ ------------------------------------------------------------------


@login_required
def categories(request: HttpRequest) -> HttpResponse:
    error = None
    if request.method == "POST":
        p = request.POST
        try:
            match p.get("action"):
                case "create":
                    ev_svc.create_category(request.user, p.get("name", ""))
                case "rename":
                    ev_svc.rename_category(request.user, p.get("id"), p.get("name", ""))
                case "delete":
                    ev_svc.delete_category(request.user, p.get("id"))
                case "up" | "down":
                    cats = list(_categories(request))
                    i = next(i for i, c in enumerate(cats) if str(c.id) == p.get("id"))
                    j = i - 1 if p["action"] == "up" else i + 1
                    if 0 <= j < len(cats):
                        if p["action"] == "up":
                            ev_svc.move_category(request.user, cats[i].id, after_id=cats[j].id)
                        else:
                            ev_svc.move_category(request.user, cats[i].id, before_id=cats[j].id)
        except ValidationError as e:
            error = " ".join(e.messages)
    space = personal_space(request.user)
    rows = [(c, c.events.filter(is_archived=False).count()) for c in _categories(request)]
    resp = render(request, "web/_categories_sheet.html", {"rows": rows, "error": error, "space": space})
    if request.method == "POST" and not error:
        resp["HX-Trigger"] = json.dumps({"yl:changed": True})
    return resp


# --- メニュー・アーカイブ ---------------------------------------------------------------


@login_required
@require_GET
def menu(request: HttpRequest) -> HttpResponse:
    archived = Event.objects.filter(space__members__user=request.user, is_archived=True).order_by("-archived_at")
    return render(request, "web/_menu_sheet.html", {"archived": archived, "user_tz": request.user.timezone})


# --- イベント詳細 ---------------------------------------------------------------------


@login_required
@require_GET
def event_detail(request: HttpRequest, event_id) -> HttpResponse:
    event = _event(request, event_id)
    today = _today(request)
    try:
        y = int(request.GET.get("y", today.year))
        m = int(request.GET.get("m", today.month))
        if not 1 <= m <= 12:
            raise ValueError
    except ValueError:
        y, m = today.year, today.month
    sel = request.GET.get("day")
    sel_date = None
    if sel:
        try:
            sel_date = date.fromisoformat(sel)
        except ValueError:
            sel_date = None
    season_all = request.GET.get("season") == "all"
    try:
        season_year = int(request.GET.get("sy", today.year))
    except ValueError:
        season_year = today.year
    season = stats.season(event, None if season_all else season_year)
    logs = event.logs.all()
    if sel_date:
        logs = logs.filter(local_date=sel_date)
    marks = stats.calendar_days(event, y, m)
    cal = calendar.Calendar(firstweekday=6).monthdatescalendar(y, m)
    prev_m = (y, m - 1) if m > 1 else (y - 1, 12)
    next_m = (y, m + 1) if m < 12 else (y + 1, 1)
    top = max(season.counts) if season.counts else 0
    ctx = {
        "event": event,
        "t": tile(event, today),
        "stats": stats.event_stats(event, today),
        "season": season,
        "season_all": season_all,
        "season_year": season_year,
        "season_bars": _season_bars(season.counts, today, None if season_all else season_year),
        "season_top": top,
        "cal_weeks": [[(d, d.month == m, d in marks, d > today) for d in week] for week in cal],
        "cal_y": y,
        "cal_m": m,
        "prev_m": prev_m,
        "next_m": next_m,
        "sel_date": sel_date,
        "today": today,
        "logs": logs[:200],
    }
    template = "web/_detail.html" if request.htmx and not request.htmx.boosted else "web/detail.html"
    return render(request, template, ctx)


def _season_bars(counts: list[int], today: date, year: int | None) -> list[dict]:
    """棒グラフ用の座標（SVG viewBox 320×150）。"""
    top = max(counts) if counts else 0
    step = 1 if top <= 4 else 2 if top <= 10 else 5 if top <= 20 else 10 if top <= 50 else 20
    ceiling = max(step, -(-top // step) * step)
    w, h, left, right, t, b = 320, 150, 22, 6, 12, 22
    cw = (w - left - right) / 12
    bw = min(16, cw * 0.56)
    bars = []
    for i, c in enumerate(counts):
        x = left + cw * i + cw / 2
        y = t + (h - t - b) * (1 - c / ceiling)
        bars.append(
            {
                "m": i + 1,
                "c": c,
                "x": round(x - bw / 2, 1),
                "y": round(y, 1),
                "w": round(bw, 1),
                "h": round(h - b - y, 1),
                "cx": round(x, 1),
                "slot_x": round(left + cw * i, 1),
                "slot_w": round(cw, 1),
                "peak": c == top and c > 0 and sum(counts) >= 3,
                "future": year == today.year and i + 1 > today.month,
            }
        )
    grid = [
        {"v": v, "y": round(t + (h - t - b) * (1 - v / ceiling), 1)}
        for v in range(0, ceiling + 1, step if ceiling / step <= 4 else step * 2)
    ]
    return {"bars": bars, "grid": grid, "base_y": h - b, "label_y": h - 6, "left": left, "right": w - right}
