"""アクセス解析（決定 047）：ログインしていない人が見る画面だけで Umami を読み込む。"""

import pytest
from django.test import override_settings

SITE = "0f1e2d3c-0000-4000-8000-123456789abc"
SCRIPT = 'src="https://cloud.umami.is/script.js"'


@pytest.mark.parametrize("path", ["/login/", "/terms/", "/privacy/"])
@override_settings(UMAMI_WEBSITE_ID=SITE)
def test_サイトIDがあれば_入口と規約の画面で解析を読み込む(client, db, path):
    body = client.get(path).content.decode()
    assert SCRIPT in body and f'data-website-id="{SITE}"' in body


@override_settings(UMAMI_WEBSITE_ID=SITE)
def test_解析はDoNotTrackを守る(client, db):
    assert 'data-do-not-track="true"' in client.get("/login/").content.decode()


@pytest.mark.parametrize("path", ["/login/", "/privacy/"])
@override_settings(UMAMI_WEBSITE_ID="")
def test_サイトIDがなければ_解析を読み込まない(client, db, path):
    assert "umami" not in client.get(path).content.decode()


@override_settings(UMAMI_WEBSITE_ID=SITE)
def test_ログインした後の画面では_解析を読み込まない(client_in):
    body = client_in.get("/").content.decode()
    assert "umami" not in body


@override_settings(UMAMI_WEBSITE_ID=SITE)
def test_ログインした人が規約を開いても_解析を読み込まない(client_in):
    assert "umami" not in client_in.get("/privacy/").content.decode()


def test_ポリシーにアクセス解析の送信先が書いてある(client, db):
    body = client.get("/privacy/").content.decode()
    assert "Umami" in body and "広告や行動分析のための外部ツールは使っていません" not in body
