from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(request: HttpRequest) -> HttpResponse:
    """死活監視用（決定 042）。DB には触れない（Neon を起こして無料枠の計算時間を使わないため）。"""
    return HttpResponse("ok", content_type="text/plain")
