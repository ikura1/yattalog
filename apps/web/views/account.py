"""自分のデータの持ち出しと、退会。"""

import json
from zoneinfo import available_timezones

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.services import delete_account, save_settings
from apps.core import clock
from apps.events.services import export as export_svc
from apps.web.views.common import clear_device_data


@login_required
@require_POST
def export(request: HttpRequest) -> HttpResponse:
    """自分の全データを ZIP でダウンロードする。その場で作るので、ファイルはどこにも残さない（決定 039）。"""
    now = clock.now()
    response = HttpResponse(export_svc.build_export(request.user, now), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{export_svc.export_filename(request.user, now)}"'
    response["Cache-Control"] = "no-store"
    return response


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
    return clear_device_data(redirect("web:login"))


# タイムゾーンの一覧。日本と、よく使われそうなものを先に、あとは名前の順
COMMON_TIMEZONES = [
    "Asia/Tokyo",
    "Asia/Seoul",
    "Asia/Shanghai",
    "Asia/Singapore",
    "America/Los_Angeles",
    "America/New_York",
    "Europe/London",
    "UTC",
]


def _timezones() -> list[str]:
    rest = sorted(z for z in available_timezones() if "/" in z and not z.startswith(("Etc/", "SystemV/")))
    return COMMON_TIMEZONES + [z for z in rest if z not in COMMON_TIMEZONES]


@login_required
def settings_sheet(request: HttpRequest) -> HttpResponse:
    """設定（週の始まり、押したときの震え、見た目、タイムゾーン。決定 066）。"""
    from apps.spaces.services import personal_space

    error = None
    if request.method == "POST":
        p = request.POST
        haptics = p.get("haptics") == "1"
        try:
            week_changed = save_settings(
                request.user,
                week_start=p.get("week_start", ""),
                theme=p.get("theme", ""),
                haptics=haptics,
                timezone=p.get("timezone", ""),
                now=clock.now(),
            )
        except ValidationError as e:
            error = " ".join(e.messages)
        else:
            resp = HttpResponse(status=204)
            trig = {
                "yl:toast": {"message": "保存しました"},
                "yl:prefs": {"theme": request.user.theme, "haptics": haptics},
            }
            if week_changed:
                trig["yl:changed"] = True
            trig["yl:close-sheet"] = True  # 閉じる合図は最後に（CLAUDE.md）
            resp["HX-Trigger"] = json.dumps(trig)
            return resp
    request.user.refresh_from_db()
    ctx = {
        "week_start": personal_space(request.user).week_start,
        "timezones": _timezones(),
        "error": error,
    }
    return render(request, "web/_settings_sheet.html", ctx)
