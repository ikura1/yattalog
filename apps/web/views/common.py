"""ビューで共通して使うもの（持ち主の確認、入力の読み取り、htmx への返事）。"""

import functools
import json
import uuid
from datetime import date, time

from django.core.exceptions import ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from apps.core import clock
from apps.events.models import Category, Event, Log
from apps.events.services import access
from apps.events.services import achievements as ach_svc
from apps.events.services import events as ev_svc
from apps.events.services.dates import today_in
from apps.events.services.logs import When


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
    return ev_svc.list_categories(request.user)


def clear_device_data(response: HttpResponse) -> HttpResponse:
    """端末に残したもの（キャッシュ、ストレージ、Service Worker）を消させる。ログアウトと退会で使う（レビュー E9）。"""
    response["Clear-Site-Data"] = '"cache", "storage"'
    return response


def _refresh(resp: HttpResponse, toast: str | None = None, **extra) -> HttpResponse:
    """htmx に「知らせを出して、ホーム（や詳細）を更新して、シートを閉じて」と伝える。

    合図は、書いた順に、操作したボタンから送られる。シートを閉じるとそのボタンが画面から消え、
    後の合図はどこにも届かなくなる。だから、シートを閉じる合図は、いちばん最後に置く。
    """
    trig: dict = {}
    if toast:
        trig["yl:toast"] = {"message": toast}
    trig["yl:changed"] = True
    trig |= {f"yl:{k.replace('_', '-')}": v for k, v in extra.items()}
    trig["yl:close-sheet"] = True
    resp["HX-Trigger"] = json.dumps(trig)  # ASCII のみ（ヘッダーに日本語をそのまま入れない）
    return resp


def _with_achievements(request: HttpRequest, message: str, log: Log | None = None) -> str:
    """操作の知らせに、新しく解除した実績を添える（決定 063）。「やった！ 記録しました　🏅 実績解除：じゅっかい」"""
    found = ach_svc.check(request.user, log)
    return f"{message}　{ach_svc.announcement(found)}" if found else message


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


NO_CATEGORY_TAB = "none"  # 「カテゴリなし」のタブの印（static/js/app.js と合わせる）


def _int_param(request, name: str, default: int, lo: int, hi: int) -> int:
    try:
        v = int(request.GET.get(name, default))
    except ValueError:
        return default
    return v if lo <= v <= hi else default
