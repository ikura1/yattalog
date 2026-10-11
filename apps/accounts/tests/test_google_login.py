"""Google ログイン（allauth の流れ）。Google とのやり取りの後、戻ってきた情報からログインを完了するところ。"""

import pytest
from allauth.core import context
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware

from apps.accounts.models import TERMS_VERSION, User
from apps.spaces.models import Space

GOOGLE_USER = {"sub": "google-sub-1", "email": "yuki@example.com", "email_verified": True, "name": "Yuki"}


def login_with_google(rf, google_user: dict):
    """Google から戻ってきた直後の状態を作り、ログインを完了させる。"""
    request = rf.get("/accounts/google/login/callback/")
    SessionMiddleware(lambda r: None).process_request(request)
    MessageMiddleware(lambda r: None).process_request(request)
    request.user = AnonymousUser()
    with context.request_context(request):
        provider = get_adapter().get_provider(request, "google")
        sociallogin = provider.sociallogin_from_response(request, google_user)
        return complete_social_login(request, sociallogin)


@pytest.mark.django_db
def test_Google_で初めてログインすると_ユーザーと個人用スペースが作られてホームへ進む(rf):
    response = login_with_google(rf, GOOGLE_USER)

    assert (response.status_code, response.url) == (302, "/")
    user = User.objects.get()
    assert (user.email, user.display_name, user.terms_version) == ("yuki@example.com", "Yuki", TERMS_VERSION)
    assert SocialAccount.objects.get(user=user).uid == "google-sub-1"
    assert Space.objects.filter(members__user=user, kind=Space.Kind.PERSONAL).count() == 1


@pytest.mark.django_db
def test_2回目のログインでは_同じユーザーのままでホームへ進む(rf):
    login_with_google(rf, GOOGLE_USER)

    response = login_with_google(rf, GOOGLE_USER)

    assert (response.status_code, response.url) == (302, "/")
    assert User.objects.count() == 1
    assert Space.objects.count() == 1


@pytest.mark.django_db
def test_メールアドレスが未確認の_Google_アカウントは_ユーザーを作らずログイン画面へ戻す(rf):
    response = login_with_google(rf, {**GOOGLE_USER, "email_verified": False})

    assert (response.status_code, response.url) == (302, "/login/")
    assert User.objects.count() == 0
