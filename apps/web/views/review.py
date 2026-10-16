"""ふりかえり（1年の草、決定 058）。"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.views.decorators.vary import vary_on_headers

from apps.events.services import events as ev_svc
from apps.events.services import review as review_svc
from apps.web.presenters import year_weeks
from apps.web.views.common import _today, owned_or_404, parse_date_or_none


@login_required
@owned_or_404
@require_GET
@vary_on_headers("HX-Request")  # htmx かどうかで、ページ全体か中身だけかが変わる
def review(request: HttpRequest) -> HttpResponse:
    """1年分の草と、選んだ日にやったこと。?event= で1つのイベントに絞る。日付が読めない・先の日なら今日。"""
    today = _today(request)
    event_id = request.GET.get("event") or None
    try:
        day = parse_date_or_none(request.GET.get("day")) or today
    except ValidationError:
        day = today
    day = min(day, today)
    year = review_svc.year_review(request.user, today, event_id)
    ctx = {
        "review": year,
        "grid": year_weeks(year, today),
        "events": ev_svc.list_events(request.user),
        "day": day,
        "day_logs": review_svc.logs_on(request.user, day, event_id),
        "year_ago": review_svc.a_year_ago(request.user, today, event_id),
        "top": [] if event_id else review_svc.top_events(request.user, today),
    }
    template = "web/_review.html" if request.htmx and not request.htmx.boosted else "web/review.html"
    return render(request, template, ctx)
