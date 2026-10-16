"""実績バッジ（SPEC 3.10、決定 020・063）。"""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from apps.events.services import achievements as ach_svc


@login_required
@require_GET
def achievements(request: HttpRequest) -> HttpResponse:
    """実績の一覧（シート）。機能が入る前からの人は、ここを開いたときにも、満たしているものを静かに解除する。"""
    ach_svc.check(request.user)
    items = ach_svc.listing(request.user)
    ctx = {"items": items, "done": sum(1 for _, at in items if at), "user_tz": request.user.timezone}
    return render(request, "web/_achievements_sheet.html", ctx)


@login_required
@require_POST
def achievement_share(request: HttpRequest) -> JsonResponse:
    """シェアした、という端末からの知らせ。シェアは端末で完結するので、ここで「シェアデビュー」を解除する。"""
    return JsonResponse({"achievement": ach_svc.announcement(ach_svc.unlock_share(request.user))})
