from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request: HttpRequest) -> HttpResponse:
    """死活監視用（決定 046）。経路は z で終わらせない（Cloud Run が /healthz などを予約していて、アプリに届かない）。
    DB には触れない（Neon を起こして無料枠の計算時間を使わないため）。"""
    return HttpResponse("ok", content_type="text/plain")
