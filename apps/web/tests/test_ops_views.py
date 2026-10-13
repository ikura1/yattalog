"""運用のための入口（死活監視、開いたままの画面を新しい版に切り替える材料）。"""


def test_ヘルスチェックの経路は_z_で終わらない():
    """Cloud Run（Google のフロントエンド）は、/healthz のように z で終わる経路の一部を横取りして 404 を返す。

    アプリまで届かないので、本番では常に落ちているように見える（2026-10-13 に本番で確認）。
    """
    from django.urls import reverse

    assert reverse("health") == "/health" and not reverse("health").endswith("z")


def test_ヘルスチェックはログインなしでDBに触れずに200を返す(client, db, django_assert_num_queries):
    with django_assert_num_queries(0):
        r = client.get("/health")
    assert r.status_code == 200 and r.content == b"ok"
    assert "Set-Cookie" not in str(r.cookies) and not r.cookies


def test_ホームの一覧は_いまのスクリプトの_URL_を持っている(client_in, event):
    """画面側は、自分が読み込んだスクリプトと見比べて、違っていたら読み込み直す。"""
    for path in ("/", "/grid/"):
        assert 'data-app-js="/static/js/app.js"' in client_in.get(path).content.decode()
