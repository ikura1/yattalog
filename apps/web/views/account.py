"""自分のデータの持ち出しと、退会。"""

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.services import delete_account
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
