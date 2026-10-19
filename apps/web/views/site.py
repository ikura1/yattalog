"""ログイン前でも開ける画面と、アプリとして追加するための情報（ログイン、規約、マニフェスト、Service Worker）。"""

import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.adapters import signup_is_full
from apps.web.views.common import clear_device_data


@require_GET
def login_page(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("web:home")
    return render(request, "web/login.html", {"signup_full": signup_is_full(), "max_users": settings.MAX_USERS})


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return clear_device_data(redirect("web:login"))  # 共用の端末に、前の人のデータを残さない


BG_LIGHT = "#EEF1F6"  # static/css/app.css の --bg と同じ


INSTALL_PLATFORMS = {"ios", "ios-other", "android"}


@require_GET
def manifest(request: HttpRequest) -> HttpResponse:
    """アプリとして追加するための情報。アイコンの URL にハッシュが付くので、ここで組み立てる。"""
    icons = [
        {"src": static(f"icons/{name}"), "sizes": f"{size}x{size}", "type": "image/png", "purpose": purpose}
        for name, size, purpose in [
            ("icon-192.png", 192, "any"),
            ("icon-512.png", 512, "any"),
            ("icon-maskable-192.png", 192, "maskable"),
            ("icon-maskable-512.png", 512, "maskable"),
        ]
    ]
    data = {
        "name": "Yattalog",
        "short_name": "Yattalog",
        "description": "前にやったのいつだっけ？ やったら1タップで記録。前回からの日数がひと目でわかる。",
        "lang": "ja",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": BG_LIGHT,
        "theme_color": BG_LIGHT,
        "icons": icons,
    }
    return HttpResponse(json.dumps(data, ensure_ascii=False), content_type="application/manifest+json")


# オフラインの案内を出すのに要るもの。Service Worker が先にしまっておく（決定 049）
SW_PRECACHE = ["css/app.css", "icons/favicon.svg", "icons/icon.svg"]


def _sw_version(urls: list[str]) -> str:
    """しまっておくものが変わったら、版も変わる。本番は URL に中身のハッシュが入っている。"""
    seed = [*urls, getattr(settings, "SW_EXTRA_VERSION", "")]
    if settings.DEBUG:
        # 開発中は URL にハッシュが入らないので、ファイルの更新時刻を混ぜる
        seed += [str(Path(found).stat().st_mtime_ns) for name in SW_PRECACHE if (found := finders.find(name))]
    return hashlib.sha256("|".join(seed).encode()).hexdigest()[:12]


@require_GET
def service_worker(request: HttpRequest) -> HttpResponse:
    """Service Worker の本体。サイト全体を受け持つので、/sw.js で返す。"""
    urls = [reverse("web:offline"), *[static(name) for name in SW_PRECACHE]]
    ctx = {"precache": urls, "version": _sw_version(urls)}
    response = render(request, "web/sw.js", ctx, content_type="text/javascript; charset=utf-8")
    response["Cache-Control"] = "no-cache"  # 古い Service Worker が残り続けないように
    response["Service-Worker-Allowed"] = "/"
    return response


@require_GET
def offline(request: HttpRequest) -> HttpResponse:
    """つながらないときに出す案内。だれが見ても同じ内容（利用者のデータを入れない）。"""
    return render(request, "web/offline.html")


@login_required
@require_GET
def install_guide(request: HttpRequest) -> HttpResponse:
    """ホーム画面に追加する方法。端末の種類は画面側（JS）で見分けて、?p= で渡す。分からなければ全部出す。"""
    platform = request.GET.get("p", "")
    return render(request, "web/_install_sheet.html", {"platform": platform if platform in INSTALL_PLATFORMS else ""})


def _legal_ctx() -> dict:
    return {
        "operator_name": settings.OPERATOR_NAME,
        "legal_date": settings.LEGAL_DATE,
        "terms_revised": settings.TERMS_REVISED,
        "privacy_revised": settings.PRIVACY_REVISED,
        "feedback_url": settings.FEEDBACK_URL,
        "contact_form_url": settings.CONTACT_FORM_URL,
    }


@require_GET
def terms(request: HttpRequest) -> HttpResponse:
    return render(request, "web/legal/terms.html", _legal_ctx())


@require_GET
def privacy(request: HttpRequest) -> HttpResponse:
    return render(request, "web/legal/privacy.html", _legal_ctx())
