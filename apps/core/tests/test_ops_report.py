"""本番の様子の報告（公開リポジトリに載せるので、利用者のデータや秘密の値を含めない）。"""

import json

from apps.core.ops_report import build_report, error_groups, route_of

UUID = "0b1c2d3e-4f50-4a6b-8c7d-9e0f1a2b3c4d"


def request(path, status=200, latency="0.050s"):
    return {
        "httpRequest": {
            "requestMethod": "GET",
            "requestUrl": f"https://yattalog.example{path}",
            "status": status,
            "latency": latency,
        }
    }


TRACEBACK = (
    f"Internal Server Error: /events/{UUID}/record/\n"
    "Traceback (most recent call last):\n"
    '  File "/app/.venv/lib/python3.14/site-packages/django/core/handlers/base.py", line 197, in _get_response\n'
    "    response = wrapped_callback(request, *callback_args, **callback_kwargs)\n"
    '  File "/app/apps/web/views.py", line 240, in record\n'
    "    log = log_svc.record(request.user, event_id, log_id)\n"
    '  File "/app/apps/events/services/logs.py", line 31, in record\n'
    "    raise ValueError(note)\n"
    "ValueError: 歯医者の予約 a@example.com\n"
)


def app_error(message=TRACEBACK):
    return {"severity": "ERROR", "jsonPayload": {"message": message, "logger": "django.request"}}


# --- 経路 -------------------------------------------------------------------------


def test_経路のIDとクエリは伏せる():
    assert route_of(f"https://h/events/{UUID}/record/?code=秘密") == "/events/<id>/record/"


def test_知らない経路は伏せる_管理画面のURLは秘密のため():
    assert route_of("https://h/manage-0123456789abcdef/auth/user/") == "/<その他>"


def test_外から選んだ単語は_経路に出さない():
    """知っている経路の後ろに好きな単語を付けて、公開の報告に落書きされないようにする（#74）。"""
    assert route_of("https://h/static/buy-cheap.example.com") == "/static/<?>"
    assert route_of("https://h/login/hello-from-attacker/") == "/login/<?>/"
    assert route_of("https://h/events/new/x.y.z") == "/events/new/<?>"


def test_アプリが使っている単語は_そのまま出す():
    assert route_of(f"https://h/events/{UUID}/record-sheet/") == "/events/<id>/record-sheet/"
    assert route_of(f"https://h/logs/{UUID}/undo/") == "/logs/<id>/undo/"
    assert route_of("https://h/accounts/google/login/callback/") == "/accounts/google/login/callback/"
    assert route_of("https://h/account/delete/") == "/account/delete/"
    assert route_of("https://h/static/css/app.0123abcd.css") == "/static/css/<?>"


def test_アプリの経路に出てくる単語は_すべて伏せずに出せる():
    """経路を足したら KNOWN_PARTS にも足す（足し忘れると、報告で <?> になる）。"""
    import re

    from django.urls import get_resolver

    from apps.core.ops_report import KNOWN_PARTS

    words = set()
    for pattern in get_resolver().url_patterns:
        if str(pattern.pattern) != "":
            continue
        for sub in pattern.url_patterns:
            literal = re.sub(r"<[^>]+>", "", str(sub.pattern))
            words |= {part for part in literal.split("/")[1:] if part}
    assert words - KNOWN_PARTS == set()


def test_トップページの経路():
    assert route_of("https://h/?x=1") == "/"


# --- エラー -----------------------------------------------------------------------


def test_エラーは例外の種類と最後に通った自前のコードでまとめる():
    groups = error_groups([app_error(), app_error()])
    assert len(groups) == 1
    g = groups[0]
    assert g.count == 2
    assert g.title == "ValueError（apps/events/services/logs.py:31 record）"
    assert g.frames == ["apps/web/views.py:240 record", "apps/events/services/logs.py:31 record"]


def test_エラーの本文と例外のメッセージは報告に含めない():
    groups = error_groups([app_error()])
    text = json.dumps([g.as_issue() for g in groups], ensure_ascii=False)
    assert "歯医者" not in text and "a@example.com" not in text and UUID not in text


def test_トレースバックのないエラーは記録元でまとめる():
    groups = error_groups([{"severity": "ERROR", "textPayload": "connection refused to 10.0.0.1"}])
    assert groups[0].title == "トレースバックのないエラー"
    assert "10.0.0.1" not in json.dumps([g.as_issue() for g in groups], ensure_ascii=False)


# --- 報告 -------------------------------------------------------------------------


def test_報告にはリクエスト数と状態ごとの数と遅い経路を出す():
    requests = [request("/"), request("/"), request(f"/events/{UUID}/record/", status=500, latency="2.5s")]
    report = build_report(requests, [app_error()], hours=24)
    assert "リクエスト：3 件" in report
    assert "5xx：1" in report
    assert "/events/<id>/record/" in report
    assert "ValueError（apps/events/services/logs.py:31 record）" in report
    assert "歯医者" not in report and UUID not in report


def test_何もなければ異常なしと書く():
    assert "異常なし" in build_report([request("/")], [], hours=24)


def test_アプリの経路はすべて伏せずに出せる():
    """経路を足したら KNOWN_ROOTS にも足す（足し忘れると、報告で /<その他> になる）。"""
    from django.conf import settings
    from django.urls import get_resolver

    from apps.core.ops_report import KNOWN_ROOTS

    admin_root = settings.ADMIN_URL.strip("/").split("/")[0]
    roots = set()
    for pattern in get_resolver().url_patterns:
        prefix = str(pattern.pattern).lstrip("^").split("/")[0]
        if prefix != admin_root:
            roots.add(prefix)
        for sub in getattr(pattern, "url_patterns", []) if prefix == "" else []:
            roots.add(str(sub.pattern).lstrip("^").split("/")[0].split("<")[0])
    assert roots - KNOWN_ROOTS == set()
