"""記録（タップ・取り消し・長押しシート・編集・削除・シェア）。"""

import uuid
from datetime import date
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.core import clock
from apps.events.models import Event, Log
from apps.events.services import logs as log_svc
from apps.events.services import share as share_svc
from apps.web.presenters import tile
from apps.web.views.common import (
    _event,
    _form_error,
    _log,
    _refresh,
    _today,
    owned_or_404,
    parse_date_or_none,
    parse_uuid,
    parse_when,
)


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
            "share_url": reverse("web:share", args=[result.log.id]),
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


def _record_ctx(request, event: Event, log: Log | None = None, **extra) -> dict:
    today = _today(request)
    return {
        "event": event,
        "log": log,
        "today": today,
        "yesterday": date.fromordinal(today.toordinal() - 1),
        "day_before": date.fromordinal(today.toordinal() - 2),
        "new_log_id": uuid.uuid7(),
        # 新しく記録するシートでだけ、さっきの記録を取り消せるようにする（編集のシートでは出さない）
        "recent": None if log else log_svc.recent_log(request.user, event.id, clock.now()),
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
    # 長押しシートの「さっきの記録を取り消す」からは、取り消しの言い方で知らせる
    return _refresh(HttpResponse(status=204), "取り消しました" if request.POST.get("undo") else "記録を削除しました")


@login_required
@owned_or_404
@require_GET
def share_sheet(request: HttpRequest, log_id) -> HttpResponse:
    """シェア画像の材料と投稿文を出す。画像は端末で作る（サーバーには送らない、決定 017・053）。"""
    info = share_svc.share_info(request.user, log_id, request.build_absolute_uri("/"))
    x_url = "https://x.com/intent/post?" + urlencode({"text": info.text})
    return render(request, "web/_share_sheet.html", {"info": info, "x_url": x_url})
