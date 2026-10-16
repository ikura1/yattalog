"""ホーム（一覧、タブ、タイムゾーン、メニュー、テンプレート）。"""

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from apps.accounts import services as account_svc
from apps.core import clock
from apps.events.services import events as ev_svc
from apps.events.services import starter as starter_svc
from apps.web.presenters import tile
from apps.web.views.common import (
    _categories,
    _form_error,
    _refresh,
    _today,
    _with_achievements,
)


def _home_ctx(request: HttpRequest) -> dict:
    today = _today(request)
    events = list(ev_svc.list_events(request.user))
    cats = list(_categories(request))
    counts = {c.id: 0 for c in cats}
    for e in events:
        if e.category_id in counts:
            counts[e.category_id] += 1
    return {
        "tiles": [tile(e, today) for e in events],
        "starters": [] if events else starter_svc.starter_choices(request.user),
        "categories": [(c, counts[c.id]) for c in cats],
        # 「カテゴリなし」のタブ（決定 050）。カテゴリがあり、入っていないイベントもあるときだけ出す
        "uncategorized": sum(1 for e in events if e.category_id is None) if cats else 0,
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
    keep = request.POST.get("action") == "keep"
    try:
        user = account_svc.set_timezone(request.user, request.POST.get("tz", ""), keep=keep, now=clock.now())
    except ValidationError as e:
        return JsonResponse({"error": " ".join(e.messages)}, status=400)
    return JsonResponse({"timezone": user.timezone})


@login_required
def starters(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        try:
            added = starter_svc.add_starters(request.user, request.POST.getlist("starter"))
        except ValidationError as e:
            ctx = {"starters": starter_svc.starter_choices(request.user)}
            return _form_error(request, "web/_starters_sheet.html", ctx, e)
        return _refresh(HttpResponse(status=204), _with_achievements(request, f"{len(added)}件を追加しました"))
    return render(request, "web/_starters_sheet.html", {"starters": starter_svc.starter_choices(request.user)})


@login_required
@require_GET
def menu(request: HttpRequest) -> HttpResponse:
    archived = ev_svc.list_archived(request.user)
    ctx = {"archived": archived, "user_tz": request.user.timezone, "feedback_url": settings.FEEDBACK_URL}
    return render(request, "web/_menu_sheet.html", ctx)
