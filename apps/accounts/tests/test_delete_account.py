"""退会（SPEC 3.11.3、決定 021・040）。データをその場ですべて消す。"""

import uuid

import pytest
from allauth.socialaccount.models import SocialAccount
from django.contrib.sessions.models import Session

from apps.accounts.models import User
from apps.accounts.services import delete_account
from apps.accounts.tests.test_google_login import GOOGLE_USER, login_with_google
from apps.core.testing import new_user
from apps.events.models import Achievement, Category, Event, Log
from apps.events.services import achievements as ach_svc
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.spaces.models import Space, SpaceMember


def with_data(user):
    category = ev_svc.create_category(user, "家事", emoji="🧹")
    event = ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", category_id=category.id)
    log = log_svc.record(user, event.id, uuid.uuid7(), memo="メモ").log
    ach_svc.check(user, log)  # 実績「はじめの一歩」も持たせる
    return user


@pytest.mark.django_db
def test_退会すると_ユーザーとそのデータがすべて消える(rf):
    login_with_google(rf, GOOGLE_USER)
    user = with_data(User.objects.get())

    delete_account(user)

    counts = [m.objects.count() for m in (User, SocialAccount, Space, SpaceMember, Category, Event, Log, Achievement)]
    assert counts == [0, 0, 0, 0, 0, 0, 0, 0]


def test_ほかの人のデータは消えない(user):
    other = with_data(new_user(email="b@example.com"))
    with_data(user)

    delete_account(user)

    assert list(User.objects.all()) == [other]
    assert (Space.objects.count(), Category.objects.count(), Event.objects.count(), Log.objects.count()) == (1, 1, 1, 1)
    assert Event.objects.get().space.members.get().user == other


@pytest.mark.django_db
def test_退会したあと_同じ_Google_アカウントで登録し直すと_空の状態から始まる(rf):
    login_with_google(rf, GOOGLE_USER)
    delete_account(with_data(User.objects.get()))

    response = login_with_google(rf, GOOGLE_USER)

    assert response.url == "/"
    assert User.objects.count() == 1 and not Event.objects.exists()


# --- 画面 ---


@pytest.fixture
def client_in(client, user):
    client.force_login(user)
    return client


def test_ログインしていなければ_退会の画面は開けない(client, db):
    assert "/login/" in client.get("/account/delete/")["Location"]
    assert "/login/" in client.post("/account/delete/", {"confirm": "on"})["Location"]


def test_メニューに退会の入口がある(client_in):
    assert "/account/delete/" in client_in.get("/menu/").content.decode()


def test_確認の画面には_消えるものと_書き出しの案内と_確認のチェックがある(client_in):
    body = client_in.get("/account/delete/").content.decode()
    assert "イベント" in body and "記録" in body and "元に戻せません" in body
    assert 'action="/export/"' in body
    assert 'name="confirm"' in body and "すべてのデータが削除され、元に戻せないことを理解しました" in body
    assert "Google アカウント" in body


def test_確認のチェックがなければ_退会しない(client_in, user):
    with_data(user)

    r = client_in.post("/account/delete/")

    assert r.status_code == 200 and "チェックを入れてください" in r.content.decode()
    assert User.objects.filter(id=user.id).exists() and Event.objects.exists()


def test_チェックを入れて退会すると_データが消えてログアウトされ_その旨が出る(client_in, user):
    with_data(user)

    r = client_in.post("/account/delete/", {"confirm": "on"}, follow=True)

    assert not User.objects.exists() and not Event.objects.exists() and not Log.objects.exists()
    assert r.redirect_chain[-1][0] == "/login/"
    assert "退会しました" in r.content.decode()
    assert "/login/" in client_in.get("/")["Location"]


def test_退会すると_ほかの端末のログインも使えなくなる(client, user):
    from django.test import Client

    phone, laptop = Client(), Client()
    phone.force_login(user)
    laptop.force_login(user)
    assert Session.objects.count() == 2

    phone.post("/account/delete/", {"confirm": "on"})

    assert "/login/" in laptop.get("/")["Location"]
