"""ログイン前の画面（はじめて来た人に、何のアプリかを伝える。決定 056）。"""

import pytest
from django.test import override_settings

from apps.core.testing import new_user


@pytest.fixture
def body(client, db) -> str:
    return client.get("/login/").content.decode()


def test_何のアプリかが_3つの場面で伝わる(body):
    assert "どんなアプリ？" in body
    for point in ("やったら、タイルを1タップ", "前にやったのは、いつ？", "やったことを、シェア"):
        assert point in body


def test_大事にしていることを_はっきり書く(body):
    assert "期限も通知もありません" in body
    assert "いつでも書き出せて" in body and "その場ですべて消えます" in body
    assert "無料" in body and "広告はありません" in body


def test_試験公開中であることと_人数の上限を伝える(body):
    assert "試験公開中" in body and "先着20人" in body


@override_settings(MAX_USERS=5)
def test_人数の上限は_設定の値を出す(client, db):
    assert "先着5人" in client.get("/login/").content.decode()


def test_ログインのボタンは_最初の画面と_いちばん下の両方にある(body):
    assert body.count("Google でログイン") == 2
    assert body.count('name="csrfmiddlewaretoken"') == 2


def test_最初の画面は_今までどおり_ロゴとひとことと_ログインのボタン(body):
    first = body.split('class="about"')[0]
    assert "前にやったのいつだっけ？" in first and "Google でログイン" in first and "利用規約" in first


@override_settings(MAX_USERS=1)
def test_満員のときは_下のボタンのそばにも_その旨を出す(client, db):
    new_user()
    body = client.get("/login/").content.decode()
    assert body.count("新しい登録を止めています") == 2


def test_見本のタイルは_飾りなので_読み上げから外す(body):
    about = body.split('class="about"')[1]
    assert about.count('aria-hidden="true"') >= 3
