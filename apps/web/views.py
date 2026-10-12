"""画面（Django テンプレート＋htmx）。処理はすべてサービス層に任せる（決定 027）。"""

import functools
import json
import uuid
from datetime import date, time

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.adapters import signup_is_full
from apps.accounts.services import delete_account
from apps.core import clock
from apps.events.models import COLORS, Category, Event, Log, StreakUnit
from apps.events.services import access, stats
from apps.events.services import events as ev_svc
from apps.events.services import export as export_svc
from apps.events.services import logs as log_svc
from apps.events.services.dates import is_valid_timezone, today_in
from apps.events.services.logs import When
from apps.spaces.services import personal_space
from apps.web.presenters import calendar_weeks, season_chart, shift_month, tile

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
    return today_in(request.user.timezone, clock.now())


NOT_YOURS = (Event.DoesNotExist, Log.DoesNotExist, Category.DoesNotExist)


def owned_or_404(view):
    """存在しない・他人のイベント／記録／カテゴリは、どの経路で見つからなくても 404 にする（レビュー S4、2回目 #8）。

    サービス層は持ち主でなければ DoesNotExist を投げる。ビューごとに try/except を書くと書き忘れが 500 になるので、
    ID を受け取るビューにはこれを付ける。
    """

    @functools.wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except NOT_YOURS:
            raise Http404 from None

    return wrapped


def _event(request: HttpRequest, event_id) -> Event:
    return access.event_for(request.user, event_id)


def _log(request: HttpRequest, log_id) -> Log:
    return access.log_for(request.user, log_id)


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


def parse_when(post) -> When:
    """フォームの「いつやった？」を When にする。壊れた値は ValidationError（500 にしない、レビュー 3）。"""
    if post.get("when", "now") == "now":
        return When()
    try:
        d = date.fromisoformat(post.get("date", ""))
    except ValueError:
        raise ValidationError("日付を選んでください", code="date") from None
    raw = (post.get("time") or "").strip()
    if not raw:
        return When(date=d)
    try:
        t = time.fromisoformat(raw)
    except ValueError:
        raise ValidationError("時刻の形式が正しくありません", code="time") from None
    return When(date=d, time=t)


def parse_date_or_none(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValidationError("日付の形式が正しくありません", code="date") from None


def parse_uuid(raw: str | None) -> uuid.UUID:
    try:
        return uuid.UUID(raw or "")
    except ValueError:
        raise ValidationError("ID の形式が正しくありません", code="id") from None


# --- ログイン・ホーム -------------------------------------------------------------


@require_GET
def login_page(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("web:home")
    return render(request, "web/login.html", {"signup_full": signup_is_full()})


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    resp = redirect("web:login")
    resp["Clear-Site-Data"] = '"cache", "storage"'  # 共用端末で前の人のデータが残らないように（レビュー E9）
    return resp


def _home_ctx(request: HttpRequest) -> dict:
    space = personal_space(request.user)
    today = _today(request)
    events = list(Event.objects.filter(space=space, is_archived=False).select_related("category").order_by("sort_key"))
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
def home(request: HttpRequest) -> HttpResponse:
    return render(request, "web/home.html", _home_ctx(request))


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
    if not is_valid_timezone(tz):
        return JsonResponse({"error": "タイムゾーンが正しくありません"}, status=400)
    user = request.user
    if request.POST.get("action") == "keep":
        user.timezone_kept_for = tz
    else:
        user.timezone = tz
    if user.onboarded_at is None:
        user.onboarded_at = clock.now()
    user.save(update_fields=["timezone", "timezone_kept_for", "onboarded_at"])
    return JsonResponse({"timezone": user.timezone})


# --- 記録（タップ・取り消し）。端末で作った ID を受け取る（決定 028） ---------------------------


def _tile_html(request, event: Event) -> str:
    return render_to_string("web/_tile.html", {"t": tile(event, _today(request))}, request=request)


@login_required
@owned_or_404
@require_POST
def record(request: HttpRequest, event_id) -> JsonResponse:
    try:
        result = log_svc.record(
            request.user,
            event_id,
            parse_uuid(request.POST.get("log_id")),
            parse_when(request.POST),
            request.POST.get("memo", ""),
        )
    except PermissionDenied as e:
        return JsonResponse({"error": str(e)}, status=409)
    except ValidationError as e:
        return JsonResponse({"error": " ".join(e.messages)}, status=422)
    t = tile(result.event, _today(request))  # タイルは1回だけ作る（レビュー 11）
    return JsonResponse(
        {
            "log_id": str(result.log.id),
            "created": result.created,
            "tile_html": render_to_string("web/_tile.html", {"t": t}, request=request),
            "streak_grew": result.streak_grew,
            "streak_text": t.streak.text if t.streak else "",
        }
    )


@login_required
@owned_or_404
@require_POST
def undo(request: HttpRequest, log_id) -> JsonResponse:
    event = log_svc.undo(request.user, log_id)
    return JsonResponse({"tile_html": _tile_html(request, event) if event else None})


# --- 長押しシート（詳しく記録）・記録の編集 -------------------------------------------------


def _record_ctx(request, event: Event, log: Log | None = None, **extra) -> dict:
    today = _today(request)
    return {
        "event": event,
        "log": log,
        "today": today,
        "yesterday": date.fromordinal(today.toordinal() - 1),
        "day_before": date.fromordinal(today.toordinal() - 2),
        "new_log_id": uuid.uuid7(),
        **extra,
    }


@login_required
@owned_or_404
def record_sheet(request: HttpRequest, event_id) -> HttpResponse:
    event = _event(request, event_id)
    if request.method == "POST":
        try:
            log_svc.record(
                request.user,
                event.id,
                parse_uuid(request.POST.get("log_id")),
                parse_when(request.POST),
                request.POST.get("memo", ""),
            )
        except PermissionDenied as e:
            return _form_error(
                request,
                "web/_record_sheet.html",
                _record_ctx(request, event, form=request.POST),
                ValidationError(str(e)),
            )
        except ValidationError as e:
            return _form_error(request, "web/_record_sheet.html", _record_ctx(request, event, form=request.POST), e)
        return _refresh(HttpResponse(status=204), "やった！ 記録しました")
    try:
        preset = parse_date_or_none(request.GET.get("date"))
    except ValidationError:
        preset = None
    return render(request, "web/_record_sheet.html", _record_ctx(request, event, preset=preset))


@login_required
@owned_or_404
def log_edit_sheet(request: HttpRequest, log_id) -> HttpResponse:
    log = _log(request, log_id)
    if request.method == "POST":
        try:
            log_svc.edit(request.user, log.id, parse_when(request.POST), request.POST.get("memo", ""))
        except ValidationError as e:
            return _form_error(
                request, "web/_record_sheet.html", _record_ctx(request, log.event, log, form=request.POST), e
            )
        return _refresh(HttpResponse(status=204), "記録を更新しました")
    return render(request, "web/_record_sheet.html", _record_ctx(request, log.event, log))


@login_required
@owned_or_404
@require_POST
def log_delete(request: HttpRequest, log_id) -> HttpResponse:
    _log(request, log_id)  # 他人の記録は 404
    log_svc.undo(request.user, log_id)
    return _refresh(HttpResponse(status=204), "記録を削除しました")


# --- イベントの追加・編集・削除・並べ替え -------------------------------------------------


def _event_form_ctx(request, event=None, form=None, **extra) -> dict:
    """フォームの初期値は、送られた値 → 編集中のイベント → 既定値 の順で決める（テンプレートでは決めない）。"""
    tab = request.GET.get("category") or request.POST.get("category") or ""
    form = form or {}

    def pick(name, default):
        return form.get(name) or (getattr(event, name) if event else None) or default

    # アイコンは、おすすめの一覧か入力欄のどちらか一方で決める（決定 035）
    if form:
        custom_emoji = (form.get("emoji_custom") or "").strip()
    else:
        custom_emoji = event.emoji if event and event.emoji not in EMOJIS else ""

    return {
        "event": event,
        "form": form,
        "cur_emoji": "" if custom_emoji else pick("emoji", EMOJIS[0]),
        "custom_emoji": custom_emoji,
        "cur_color": pick("color", "sky"),
        "cur_unit": pick("streak_unit", StreakUnit.DAY),
        "emojis": EMOJIS,
        "colors": COLORS,
        "units": UNITS,
        "categories": _categories(request),
        "selected_category": str(event.category_id) if event and event.category_id else tab,
        "today": _today(request),
        **extra,
    }


def _posted_emoji(post) -> str:
    """入力欄に入っていればそれを、なければおすすめの一覧で選んだものを使う。"""
    return (post.get("emoji_custom") or "").strip() or post.get("emoji", "")


@login_required
def event_new(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        p = request.POST
        try:
            ev_svc.create_event(
                request.user,
                name=p.get("name", ""),
                emoji=_posted_emoji(p),
                color=p.get("color", ""),
                streak_unit=p.get("streak_unit", StreakUnit.DAY),
                category_id=p.get("category") or None,
                last_done=parse_date_or_none(p.get("last_done")),
            )
        except ValidationError as e:
            return _form_error(request, "web/_event_sheet.html", _event_form_ctx(request, form=p), e)
        return _refresh(HttpResponse(status=204), "追加しました")
    return render(request, "web/_event_sheet.html", _event_form_ctx(request))


@login_required
@owned_or_404
def event_edit(request: HttpRequest, event_id) -> HttpResponse:
    event = _event(request, event_id)
    if request.method == "POST":
        p = request.POST
        try:
            ev_svc.update_event(
                request.user,
                event.id,
                name=p.get("name", ""),
                emoji=_posted_emoji(p),
                color=p.get("color", ""),
                streak_unit=p.get("streak_unit", StreakUnit.DAY),
                category_id=p.get("category") or None,
            )
        except ValidationError as e:
            return _form_error(request, "web/_event_sheet.html", _event_form_ctx(request, event, form=p), e)
        return _refresh(HttpResponse(status=204), "保存しました")
    return render(request, "web/_event_sheet.html", _event_form_ctx(request, event))


@login_required
@owned_or_404
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
@owned_or_404
@require_POST
def event_restore(request: HttpRequest, event_id) -> HttpResponse:
    ev_svc.set_archived(request.user, event_id, False)
    return _refresh(HttpResponse(status=204), "ホームに戻しました")


@login_required
@owned_or_404
@require_POST
def event_move(request: HttpRequest, event_id) -> HttpResponse:
    try:
        ev_svc.move_event(
            request.user,
            event_id,
            before_id=request.POST.get("before") or None,
            after_id=request.POST.get("after") or None,
        )
    except ValidationError:
        return HttpResponse(status=422)
    return HttpResponse(status=204)


# --- カテゴリ ------------------------------------------------------------------


@login_required
@owned_or_404
def categories(request: HttpRequest) -> HttpResponse:
    error = None
    if request.method == "POST":
        p = request.POST
        action = p.get("action")
        try:
            match action:
                case "create":
                    ev_svc.create_category(request.user, p.get("name", ""), p.get("emoji", ""))
                case "rename":
                    ev_svc.rename_category(request.user, p.get("id"), p.get("name", ""), p.get("emoji"))
                case "delete":
                    ev_svc.delete_category(request.user, p.get("id"))
                case "up" | "down":
                    ev_svc.shift_category(request.user, p.get("id"), -1 if action == "up" else 1)
                case _:
                    return HttpResponse(status=400)
        except ValidationError as e:
            error = " ".join(e.messages)
    rows = [(c, c.events.filter(is_archived=False).count()) for c in _categories(request)]
    resp = render(request, "web/_categories_sheet.html", {"rows": rows, "error": error})
    if request.method == "POST" and not error:
        resp["HX-Trigger"] = json.dumps({"yl:changed": True})
    return resp


# --- メニュー・アーカイブ ---------------------------------------------------------------


@login_required
@require_GET
def menu(request: HttpRequest) -> HttpResponse:
    archived = Event.objects.filter(space__members__user=request.user, is_archived=True).order_by("-archived_at")
    return render(request, "web/_menu_sheet.html", {"archived": archived, "user_tz": request.user.timezone})


# --- データの書き出し -----------------------------------------------------------------


@login_required
@require_POST
def export(request: HttpRequest) -> HttpResponse:
    """自分の全データを ZIP でダウンロードする。その場で作るので、ファイルはどこにも残さない（決定 039）。"""
    now = clock.now()
    response = HttpResponse(export_svc.build_export(request.user, now), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{export_svc.export_filename(request.user, now)}"'
    response["Cache-Control"] = "no-store"
    return response


# --- 退会 -----------------------------------------------------------------------------

LEFT = "退会しました。データはすべて削除しました。ご利用ありがとうございました。"


@login_required
def account_delete(request: HttpRequest) -> HttpResponse:
    """確認の画面を出し、確認のチェックが入っていたら、その場で全データを消す（決定 040）。"""
    if request.method != "POST":
        return render(request, "web/_account_delete_sheet.html")
    if request.POST.get("confirm") != "on":
        error = "退会するには、確認のチェックを入れてください。"
        return render(request, "web/account_delete.html", {"error": error})
    user = request.user
    logout(request)
    delete_account(user)
    messages.success(request, LEFT)
    resp = redirect("web:login")
    resp["Clear-Site-Data"] = '"cache", "storage"'  # 端末に残ったデータも消す（ログアウトと同じ）
    return resp


# --- イベント詳細 ---------------------------------------------------------------------


def _int_param(request, name: str, default: int, lo: int, hi: int) -> int:
    try:
        v = int(request.GET.get(name, default))
    except ValueError:
        return default
    return v if lo <= v <= hi else default


@login_required
@owned_or_404
@require_GET
def event_detail(request: HttpRequest, event_id) -> HttpResponse:
    event = _event(request, event_id)
    today = _today(request)
    y = _int_param(request, "y", today.year, 1900, 9999)
    m = _int_param(request, "m", today.month, 1, 12)
    season_all = request.GET.get("season") == "all"
    season_year = _int_param(request, "sy", today.year, 1900, 9999)
    try:
        sel_date = parse_date_or_none(request.GET.get("day"))
    except ValidationError:
        sel_date = None
    season = stats.season(event, None if season_all else season_year)
    logs = event.logs.all()
    if sel_date:
        logs = logs.filter(local_date=sel_date)
    ctx = {
        "event": event,
        "t": tile(event, today),
        "stats": stats.event_stats(event, today),
        "season": season,
        "season_all": season_all,
        "season_year": season_year,
        "chart": season_chart(season.counts, today, None if season_all else season_year),
        "cal_weeks": calendar_weeks(y, m, stats.calendar_days(event, y, m), today),
        "cal_y": y,
        "cal_m": m,
        "prev_m": shift_month(y, m, -1),
        "next_m": shift_month(y, m, 1),
        "sel_date": sel_date,
        "today": today,
        "logs": logs[:200],
    }
    template = "web/_detail.html" if request.htmx and not request.htmx.boosted else "web/detail.html"
    return render(request, template, ctx)
