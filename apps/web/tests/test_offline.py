"""オフラインでも開けるようにする仕組み（Service Worker、SPEC 3.12、レビュー E9、決定 049）。

キャッシュに入れてよいのは、だれが見ても同じもの（静的ファイルと、オフラインの案内）だけ。
ログインした人の画面は、キャッシュに入れない（共用の端末で、ほかの人に見えてしまうため）。
"""

import pytest


@pytest.fixture
def sw(client, db) -> str:
    return client.get("/sw.js").content.decode()


def test_Service_Worker_は_ログインしなくても取れる_JavaScript(client, db):
    r = client.get("/sw.js")
    assert r.status_code == 200 and r["Content-Type"].startswith("text/javascript")


def test_Service_Worker_自体は_キャッシュさせない(client, db):
    """古い Service Worker が残り続けないよう、ブラウザには毎回確かめてもらう。"""
    assert "no-cache" in client.get("/sw.js")["Cache-Control"]


def test_Service_Worker_は_サイト全体を受け持つ(client, db):
    r = client.get("/sw.js")
    assert r["Service-Worker-Allowed"] == "/"


def test_オフラインの案内は_ログインしなくても開けて_利用者のデータを含まない(client, db):
    r = client.get("/offline/")
    body = r.content.decode()
    assert r.status_code == 200 and "オフラインです" in body and "もう一度開く" in body
    assert "Set-Cookie" not in r.headers


def test_先にしまっておくのは_オフラインの案内と_その表示に要るものだけ(sw):
    assert '"/offline/"' in sw
    assert "/static/css/app" in sw and "/static/icons/" in sw
    for private in ("/grid/", "/menu/", "/events/", "/logs/", "/export/", "/account/", "/accounts/"):
        assert f'"{private}' not in sw


def test_画面の移動は_必ずネットワークに取りに行き_だめなときだけ案内を出す(sw):
    assert 'request.mode === "navigate"' in sw
    assert "fetch(request).catch(" in sw and 'caches.match("/offline/")' in sw


def test_キャッシュに入れるのは_static_の下だけ(sw):
    assert 'url.pathname.startsWith("/static/")' in sw
    assert sw.count("cache.put(") == 1


def test_GET_以外と_よそのサイトへの通信には_手を出さない(sw):
    assert 'request.method !== "GET"' in sw and "url.origin !== self.location.origin" in sw


def test_中身が変わると_Service_Worker_の版も変わる(client, db, settings):
    """静的ファイルが変われば別の版になり、古いキャッシュは捨てられる。"""
    before = client.get("/sw.js").content.decode()
    assert "const VERSION = " in before and "caches.delete(" in before

    settings.SW_EXTRA_VERSION = "changed"

    assert client.get("/sw.js").content.decode() != before


def test_どのページからも_Service_Worker_を登録する(client, db):
    from pathlib import Path

    from django.conf import settings as conf

    js = (Path(conf.BASE_DIR) / "static" / "js" / "app.js").read_text()
    assert 'navigator.serviceWorker.register("/sw.js")' in js
