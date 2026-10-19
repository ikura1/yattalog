"""Google ログイン（allauth の流れ）。Google とのやり取りの後、戻ってきた情報からログインを完了するところ。"""

import pytest
from allauth.core import context
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import override_settings

from apps.accounts.models import TERMS_VERSION, User
from apps.core.testing import new_user
from apps.spaces.models import Space

GOOGLE_USER = {"sub": "google-sub-1", "email": "yuki@example.com", "email_verified": True, "name": "Yuki"}


def login_with_google(rf, google_user: dict):
    """Google から戻ってきた直後の状態を作り、ログインを完了させる。"""
    return login_and_messages(rf, google_user)[0]


def login_and_messages(rf, google_user: dict):
    """ログインを完了させ、(レスポンス, 画面に出すメッセージ) を返す。"""
    request = rf.get("/accounts/google/login/callback/")
    SessionMiddleware(lambda r: None).process_request(request)
    MessageMiddleware(lambda r: None).process_request(request)
    request.user = AnonymousUser()
    with context.request_context(request):
        provider = get_adapter().get_provider(request, "google")
        sociallogin = provider.sociallogin_from_response(request, google_user)
        response = complete_social_login(request, sociallogin)
    return response, [str(m) for m in get_messages(request)]


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


# --- 登録できる人数の上限（決定 038） ---


def google_user(n: int) -> dict:
    return {**GOOGLE_USER, "sub": f"google-sub-{n}", "email": f"user{n}@example.com"}


@pytest.mark.django_db
@override_settings(MAX_USERS=2)
def test_上限までは登録でき_超えたら登録せずに満員と知らせる(rf):
    assert login_with_google(rf, google_user(1)).url == "/"
    assert login_with_google(rf, google_user(2)).url == "/"

    response, messages = login_and_messages(rf, google_user(3))

    assert (response.status_code, response.url) == (302, "/login/")
    assert User.objects.count() == 2
    assert len(messages) == 1 and "満員" in messages[0]


@pytest.mark.django_db
@override_settings(MAX_USERS=1)
def test_満員でも_登録済みの人はログインできる(rf):
    login_with_google(rf, GOOGLE_USER)

    response = login_with_google(rf, GOOGLE_USER)

    assert (response.status_code, response.url) == (302, "/")


@pytest.mark.django_db
@override_settings(MAX_USERS=1)
def test_退会の手続き中の人は_人数に数えない(rf):
    leaving = new_user(email="bye@example.com")
    leaving.is_active = False
    leaving.save()

    assert login_with_google(rf, GOOGLE_USER).url == "/"


@pytest.mark.django_db
@override_settings(MAX_USERS=1)
def test_満員のとき_ログイン画面に_新規登録を止めていることが出る(client):
    assert "新しい登録を止めています" not in client.get("/login/").content.decode()
    new_user()

    body = client.get("/login/").content.decode()

    assert "新しい登録を止めています" in body and "Google でログイン" in body


# --- Google から受け取った情報のうち、保存するもの（プライバシーポリシー 2章） ---

GOOGLE_USER_FULL = {
    **GOOGLE_USER,
    "picture": "https://lh3.googleusercontent.com/a/photo",
    "given_name": "Yuki",
    "family_name": "Ikura",
    "locale": "ja",
}


@pytest.mark.django_db
def test_初めてのログインで_プロフィール画像などポリシーにない情報は保存しない(rf):
    login_with_google(rf, GOOGLE_USER_FULL)

    assert SocialAccount.objects.get().extra_data == GOOGLE_USER


@pytest.mark.django_db
def test_2回目のログインでも_プロフィール画像などポリシーにない情報は保存しない(rf):
    login_with_google(rf, GOOGLE_USER)

    login_with_google(rf, GOOGLE_USER_FULL)

    assert SocialAccount.objects.get().extra_data == GOOGLE_USER


@pytest.mark.django_db
def test_保存済みの_ポリシーにない情報は_マイグレーションで消える(rf):
    from importlib import import_module

    from django.apps import apps

    login_with_google(rf, GOOGLE_USER)
    SocialAccount.objects.update(extra_data=GOOGLE_USER_FULL)

    import_module("apps.accounts.migrations.0003_trim_google_extra_data").trim_extra_data(apps, None)

    assert SocialAccount.objects.get().extra_data == GOOGLE_USER
