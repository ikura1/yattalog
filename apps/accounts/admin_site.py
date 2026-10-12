"""管理画面の入口（レビュー S10、決定 045）。

入れるのは、設定（ADMIN_EMAILS）にあるメールアドレスの人が、Google でログインし、
さらに2段階認証（認証アプリの6桁のコード）を通したときだけ。パスワードでのログインは使わない。
"""

from base64 import b32encode
from functools import update_wrapper

import django_otp
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.accounts.services import is_admin, sync_admin_flag

DEVICE_NAME = "認証アプリ"
WRONG_CODE = (
    "コードが違います。認証アプリに出ている、いまの6桁を入れてください。"
    "続けて間違えると、少しの間、受け付けなくなります。"
)


class SecureAdminSite(admin.AdminSite):
    site_header = "Yattalog 管理"
    site_title = "Yattalog 管理"
    index_title = "管理"

    def has_permission(self, request: HttpRequest) -> bool:
        return is_admin(request.user) and request.user.is_verified()

    def _stop(self, request: HttpRequest) -> HttpResponse | None:
        """入れない人を止める。管理者でない人には、管理画面があることも見せない（404）。"""
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        if not is_admin(request.user):
            raise Http404
        sync_admin_flag(request.user)
        return None

    def admin_view(self, view, cacheable=False):
        inner = super().admin_view(view, cacheable)

        def gate(request, *args, **kwargs):
            if (stopped := self._stop(request)) is not None:
                return stopped
            if not request.user.is_verified():
                return redirect("admin:otp")
            return inner(request, *args, **kwargs)

        return update_wrapper(gate, view)

    def login(self, request, extra_context=None):
        """Django 標準のパスワードのログイン画面は出さない。"""
        if (stopped := self._stop(request)) is not None:
            return stopped
        return redirect("admin:index" if request.user.is_verified() else "admin:otp")

    def get_urls(self):
        return [path("otp/", self.otp_view, name="otp"), *super().get_urls()]

    @method_decorator(never_cache)
    def otp_view(self, request: HttpRequest) -> HttpResponse:
        """2段階認証。はじめてのときは認証アプリへの登録、2回目からはコードの入力だけ。"""
        if (stopped := self._stop(request)) is not None:
            return stopped
        device = TOTPDevice.objects.filter(user=request.user).order_by("-confirmed", "id").first()
        if device is None:
            device = TOTPDevice.objects.create(user=request.user, name=DEVICE_NAME, confirmed=False)
        error = ""
        if request.method == "POST":
            code = "".join(ch for ch in request.POST.get("code", "") if ch.isdigit())
            if code and device.verify_token(code):
                if not device.confirmed:
                    device.confirmed = True
                    device.save(update_fields=["confirmed"])
                django_otp.login(request, device)
                return redirect("admin:index")
            error = WRONG_CODE
        ctx = {"error": error, "setup": not device.confirmed}
        if not device.confirmed:
            # 鍵を見せるのは、登録が済むまで。済んだあとは、どの画面にも出さない
            ctx |= {"config_url": device.config_url, "secret": b32encode(device.bin_key).decode()}
        return render(request, "admin/otp.html", ctx)
