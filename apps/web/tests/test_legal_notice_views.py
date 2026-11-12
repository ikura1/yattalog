"""ホームに出す、規約とポリシーの改定の知らせ（決定 073）。"""

import pytest

from apps.accounts.models import PRIVACY_VERSION, TERMS_VERSION

pytestmark = pytest.mark.django_db

URL = "/notices/legal/"


@pytest.fixture
def outdated(user):
    """ポリシーが改定される前に登録した人。"""
    user.terms_version, user.privacy_version = TERMS_VERSION, "2026-10-17"
    user.save(update_fields=["terms_version", "privacy_version"])
    return user


def test_改定があると_ホームに知らせと本文へのリンクが出る(client_in, outdated, settings):
    settings.PRIVACY_CHANGE = "健康に関する記録の扱いを書き足しました"

    html = client_in.get("/").content.decode()

    assert 'id="legalBanner"' in html
    assert '<a href="/privacy/">プライバシーポリシー</a>を改定しました' in html
    assert "健康に関する記録の扱いを書き足しました" in html
    assert "利用規約</a>を改定しました" not in html


def test_改定がなければ_知らせは出ない(client_in, user):
    user.terms_version, user.privacy_version = TERMS_VERSION, PRIVACY_VERSION
    user.save(update_fields=["terms_version", "privacy_version"])

    assert 'id="legalBanner"' not in client_in.get("/").content.decode()


def test_閉じると_空の応答が返り_次からは出ない(client_in, outdated):
    res = client_in.post(URL)

    assert (res.status_code, res.content) == (200, b"")
    assert 'id="legalBanner"' not in client_in.get("/").content.decode()


def test_閉じるのは_POST_だけ(client_in, outdated):
    assert client_in.get(URL).status_code == 405


def test_ログインしていなければ_閉じられない(client, outdated):
    assert client.post(URL).status_code == 302


def test_一覧だけの差し替えには_知らせを入れない(client_in, outdated):
    """知らせは一覧の外に置く。一覧を読み直しても、閉じた知らせが戻らない。"""
    assert "legalBanner" not in client_in.get("/grid/").content.decode()
