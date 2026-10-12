"""django-allauth のアダプタ。Google ログインのみ（決定 016）、識別は sub（レビュー S3）。"""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone

from apps.accounts.models import PRIVACY_VERSION, TERMS_VERSION, User

SIGNUP_FULL = "ただいま満員のため、新しい登録を止めています。登録済みの方は、そのままログインできます。"


def signup_is_full() -> bool:
    """登録できる人数の上限に達しているか（決定 038）。退会の手続き中の人は数えない。"""
    return User.objects.filter(is_active=True).count() >= settings.MAX_USERS


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request) -> bool:
        # パスワードでの登録はしない。ソーシャルログイン経由の登録だけを許可する
        return False


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin) -> bool:
        return not signup_is_full()

    def pre_social_login(self, request, sociallogin) -> None:
        data = sociallogin.account.extra_data or {}
        if sociallogin.account.provider == "google" and not data.get("email_verified", False):
            messages.error(request, "確認済みのメールアドレスを持つ Google アカウントでログインしてください。")
            raise ImmediateHttpResponse(redirect("web:login"))
        if not sociallogin.is_existing and signup_is_full():
            messages.error(request, SIGNUP_FULL)
            raise ImmediateHttpResponse(redirect("web:login"))
        user = sociallogin.user
        if user.pk and not user.is_active:
            messages.error(request, "このアカウントは退会の手続き中です。")
            raise ImmediateHttpResponse(redirect("web:login"))

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        extra = sociallogin.account.extra_data or {}
        user.display_name = (extra.get("name") or data.get("name") or "")[:100]
        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        # ランディングの「続けると、利用規約とプライバシーポリシーに同意したことになります」に対応する記録
        user.terms_version = TERMS_VERSION
        user.privacy_version = PRIVACY_VERSION
        user.terms_accepted_at = timezone.now()
        user.save(update_fields=["terms_version", "privacy_version", "terms_accepted_at"])

        from apps.spaces.services import ensure_personal_space

        ensure_personal_space(user)
        return user
