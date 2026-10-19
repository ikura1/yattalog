"""ログインの要否と、セキュリティのヘッダー（HTTP としての約束）。"""

import uuid

from apps.events.models import Log


def test_ログインしていなければログイン画面へ(client, db):
    r = client.get("/")
    assert r.status_code == 302 and "/login/" in r["Location"]


def test_ログイン画面にGoogleログインのボタンがある(client, db):
    assert "Google でログイン" in client.get("/login/").content.decode()


def test_ホームにイベントが並ぶ(client_in, event):
    body = client_in.get("/").content.decode()
    assert "シーツ交換" in body and "まだ" in body


def test_CSRFトークンのないPOSTは拒否され_トークンをヘッダーで送れば通る(user, event):
    from django.test import Client

    browser = Client(enforce_csrf_checks=True)  # 通常のテスト用クライアントは CSRF の検査を省くので、検査ありで確かめる
    browser.force_login(user)
    url = f"/events/{event.id}/record/"

    assert browser.post(url, {"log_id": str(uuid.uuid4())}).status_code == 403
    assert not Log.objects.exists()

    browser.get("/")  # ページを開くとトークンが配られる。htmx と fetch は、これをヘッダーで送り返す
    token = browser.cookies["csrftoken"].value
    assert browser.post(url, {"log_id": str(uuid.uuid4())}, HTTP_X_CSRFTOKEN=token).status_code == 200
    assert Log.objects.count() == 1


def test_CSPでインラインスクリプトを禁止している(client_in, event):
    csp = client_in.get("/")["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp and "frame-ancestors 'none'" in csp


def test_ログアウトはPOSTだけで端末のデータも消す(client_in):
    assert client_in.get("/logout/").status_code == 405
    r = client_in.post("/logout/")
    assert r.status_code == 302 and "Clear-Site-Data" in r


def test_ログアウトでは_端末のストレージだけを消させる_キャッシュの消去は遅いので頼まない(client_in):
    """Chrome などは "cache" の消去に数秒かかり、ログアウトが止まったように見えていた（2026-10-19）。"""
    r = client_in.post("/logout/")
    assert r["Clear-Site-Data"] == '"storage"'


def test_ログイン中の画面は_ブラウザに保存させない(client_in, event):
    """共用の端末で、ログアウトのあと「戻る」やキャッシュから、前の人の画面が見えないように。"""
    for url in ("/", f"/events/{event.id}/", "/review/", "/menu/"):
        cache = client_in.get(url)["Cache-Control"]
        assert "no-store" in cache and "private" in cache, url


def test_ログインしていない人の画面は_保存を止めない(client, db):
    assert "no-store" not in client.get("/login/").get("Cache-Control", "")
