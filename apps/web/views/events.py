"""イベントとカテゴリ（追加・編集・削除・並べ替え・詳細）。"""

import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from apps.events.models import COLORS, StreakUnit
from apps.events.services import events as ev_svc
from apps.events.services import stats
from apps.web.presenters import calendar_weeks, month_day_cells, season_chart, shift_month, tendency_bars, tile
from apps.web.views.common import (
    NO_CATEGORY_TAB,
    _categories,
    _event,
    _form_error,
    _int_param,
    _refresh,
    _today,
    owned_or_404,
    parse_date_or_none,
)

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
HISTORY_PAGE = 20  # 記録の履歴は、はじめこの件数だけ出し、「もっと見る」で増やす（詳細が縦に長くならないように）


def _event_form_ctx(request, event=None, form=None, **extra) -> dict:
    """フォームの初期値は、送られた値 → 編集中のイベント → 既定値 の順で決める（テンプレートでは決めない）。"""
    tab = request.GET.get("category") or request.POST.get("category") or ""
    if tab == NO_CATEGORY_TAB:
        tab = ""  # 「カテゴリなし」のタブから追加するときは、カテゴリを付けない
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
    shown = _int_param(request, "n", HISTORY_PAGE, HISTORY_PAGE, 2000)
    left = logs.count() - shown
    more = request.GET.copy()
    more["n"] = shown + HISTORY_PAGE
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
        "logs": logs[:shown],
        "more_url": f"?{more.urlencode()}" if left > 0 else "",
        "more_left": left,
        "latest_log": event.logs.first(),  # 「シェア」の対象（最新の記録）
        # そのイベントのくせ（決定 060）
        "weekdays": (weekdays := stats.weekday_tendency(event)),
        "weekday_bars": tendency_bars(weekdays),
        "times": (times := stats.time_tendency(event)),
        "time_bars": tendency_bars(times),
        "mdays": (mdays := stats.month_days(event)),
        "mday_cells": month_day_cells(mdays),
    }
    template = "web/_detail.html" if request.htmx and not request.htmx.boosted else "web/detail.html"
    return render(request, template, ctx)
