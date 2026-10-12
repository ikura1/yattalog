from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request: HttpRequest) -> HttpResponse:
    """死活監視用（決定 046）。DB には触れない（Neon を起こして無料枠の計算時間を使わないため）。

    経路は /health。/healthz にしてはいけない：Cloud Run は z で終わる経路の一部を横取りして、
    アプリに届く前に 404 を返す。
    """
    return HttpResponse("ok", content_type="text/plain")
