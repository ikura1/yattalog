"""画面（ビュー）の振る舞い。処理の中身はサービス層のテストで確かめ、ここでは HTTP としての約束を確かめる。"""

import json
import uuid

import pytest

from apps.events.models import Event, Log
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc


@pytest.fixture
def client_in(client, user):
    client.raise_request_exception = False  # 500 を例外ではなくレスポンスとして確かめる
    client.force_login(user)
    return client


@pytest.fixture
def event(user):
    return ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week")


# --- 認証・ヘッダー --------------------------------------------------------------


def test_ログインしていなければログイン画面へ(client, db):
    r = client.get("/")
    assert r.status_code == 302 and "/login/" in r["Location"]


def test_ログイン画面にGoogleログインのボタンがある(client, db):
    assert "Google でログイン" in client.get("/login/").content.decode()


def test_ホームにイベントが並ぶ(client_in, event):
    body = client_in.get("/").content.decode()
    assert "シーツ交換" in body and "まだ" in body


def test_CSPでインラインスクリプトを禁止している(client_in, event):
    csp = client_in.get("/")["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp and "frame-ancestors 'none'" in csp


def test_ログアウトはPOSTだけで端末のデータも消す(client_in):
    assert client_in.get("/logout/").status_code == 405
    r = client_in.post("/logout/")
    assert r.status_code == 302 and "Clear-Site-Data" in r


# --- 記録 ----------------------------------------------------------------------


def test_同じIDで2回記録しても1件(client_in, event):
    lid = str(uuid.uuid4())
    r1 = client_in.post(f"/events/{event.id}/record/", {"log_id": lid})
    r2 = client_in.post(f"/events/{event.id}/record/", {"log_id": lid})
    assert (r1.json()["created"], r2.json()["created"]) == (True, False)
    assert Log.objects.count() == 1 and "今日" in r1.json()["tile_html"]


def test_取り消すと記録が消える(client_in, event):
    lid = str(uuid.uuid4())
    client_in.post(f"/events/{event.id}/record/", {"log_id": lid})
    assert client_in.post(f"/logs/{lid}/undo/").status_code == 200
    assert Log.objects.count() == 0


@pytest.mark.parametrize(
    "data",
    [
        {"log_id": "x"},
        {"log_id": ""},
        {"when": "pick", "date": "2026-13-01"},
        {"when": "pick", "date": ""},
        {"when": "pick", "date": "2026-01-01", "time": "25:99"},
        {"when": "pick", "date": "2999-01-01"},
        {"memo": "あ" * 1001},
    ],
    ids=[
        "IDが壊れている",
        "IDが空",
        "日付が壊れている",
        "日付が空",
        "時刻が壊れている",
        "未来の日付",
        "メモが長すぎる",
    ],
)
def test_壊れた入力の記録は422で記録されない(client_in, event, data):
    payload = {"log_id": str(uuid.uuid4()), **data}
    r = client_in.post(f"/events/{event.id}/record/", payload)
    assert r.status_code == 422 and "error" in r.json()
    assert Log.objects.count() == 0


def test_長押しシートから昨日の時刻なしで記録できる(client_in, event):
    r = client_in.post(
        f"/events/{event.id}/record-sheet/",
        {"log_id": str(uuid.uuid4()), "when": "pick", "date": "2026-10-09", "time": "", "memo": "メモ"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204
    trig = json.loads(r["HX-Trigger"])
    assert trig["yl:changed"] and trig["yl:close-sheet"]
    log = Log.objects.get()
    assert (str(log.local_date), log.occurred_at, log.memo) == ("2026-10-09", None, "メモ")


def test_長押しシートで壊れた時刻はフォームにエラーを出す(client_in, event):
    r = client_in.post(
        f"/events/{event.id}/record-sheet/",
        {"log_id": str(uuid.uuid4()), "when": "pick", "date": "2026-10-09", "time": "99:00"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200 and "時刻の形式" in r.content.decode()


def test_長押しシートは昨日と一昨日の日付をサーバーから渡す(client_in, event):
    body = client_in.get(f"/events/{event.id}/record-sheet/").content.decode()
    assert 'data-yesterday="2026-10-09"' in body and 'data-day-before="2026-10-08"' in body


# --- 他人のデータ（レビュー S4） ------------------------------------------------------


@pytest.fixture
def theirs(other_user):
    e = ev_svc.create_event(other_user, name="散髪", emoji="✂️", color="grape")
    lid = uuid.uuid4()
    log_svc.record(other_user, e.id, lid)
    return e, lid


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/events/{e}/"),
        ("get", "/events/{e}/record-sheet/"),
        ("post", "/events/{e}/record/"),
        ("get", "/events/{e}/edit/"),
        ("post", "/events/{e}/remove/"),
        ("post", "/events/{e}/restore/"),
        ("post", "/events/{e}/move/"),
        ("get", "/logs/{l}/edit/"),
        ("post", "/logs/{l}/delete/"),
    ],
)
def test_他人のイベントと記録は404(client_in, theirs, method, path):
    e, lid = theirs
    r = getattr(client_in, method)(path.format(e=e.id, l=lid), {"log_id": str(uuid.uuid4()), "action": "delete"})
    assert r.status_code == 404
    assert Event.objects.filter(id=e.id).exists() and Log.objects.filter(id=lid).exists()


def test_他人の記録の取り消しは何も起きない(client_in, theirs):
    _, lid = theirs
    assert client_in.post(f"/logs/{lid}/undo/").json() == {"tile_html": None}
    assert Log.objects.filter(id=lid).exists()


@pytest.mark.parametrize("action", ["up", "down", "rename", "delete"])
def test_他人や存在しないカテゴリの操作は404(client_in, other_user, action):
    theirs = ev_svc.create_category(other_user, "趣味")
    for cid in (theirs.id, uuid.uuid4()):
        r = client_in.post("/categories/", {"action": action, "id": str(cid), "name": "x"})
        assert r.status_code == 404


def test_並べ替えの位置に他人のイベントを渡すと422(client_in, user, theirs, event):
    other, _ = theirs
    assert client_in.post(f"/events/{event.id}/move/", {"before": str(other.id)}).status_code == 422


# --- イベント・タイムゾーン --------------------------------------------------------------


def test_前回やった日つきでイベントを作り詳細を開ける(client_in):
    r = client_in.post(
        "/events/new/",
        {"name": "散髪", "emoji": "✂️", "color": "grape", "streak_unit": "month", "last_done": "2026-09-01"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204
    e = Event.objects.get(name="散髪")
    assert "よくやる時期" in client_in.get(f"/events/{e.id}/").content.decode()


def test_前回やった日が壊れていたらフォームにエラーを出す(client_in):
    r = client_in.post(
        "/events/new/",
        {"name": "散髪", "emoji": "✂️", "color": "grape", "streak_unit": "month", "last_done": "nope"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200 and not Event.objects.exists()


def test_詳細の壊れたクエリは無視して表示する(client_in, event):
    r = client_in.get(f"/events/{event.id}/?y=abc&m=13&sy=x&day=nope")
    assert r.status_code == 200


def test_タイムゾーンを設定できる(client_in, user):
    assert client_in.post("/timezone/", {"tz": "America/Los_Angeles"}).status_code == 200
    user.refresh_from_db()
    assert user.timezone == "America/Los_Angeles" and user.onboarded_at is not None


def test_正しくないタイムゾーンは400(client_in, user):
    assert client_in.post("/timezone/", {"tz": "Not/AZone"}).status_code == 400


def test_DBのソートキーが壊れていても並べ替えは500ではなく422(client_in, user, event):
    other = ev_svc.create_event(user, name="散髪", emoji="✂️", color="grape")
    Event.objects.filter(id=other.id).update(sort_key="!!")
    assert client_in.post(f"/events/{event.id}/move/", {"after": str(other.id)}).status_code == 422


@pytest.mark.parametrize("path", ["/events/{id}/", "/events/{id}/edit/", "/events/{id}/restore/", "/logs/{id}/edit/"])
def test_存在しないIDは404(client_in, path):
    method = client_in.post if path.endswith("restore/") else client_in.get
    assert method(path.format(id=uuid.uuid4())).status_code == 404
