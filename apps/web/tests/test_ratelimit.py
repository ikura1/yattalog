"""レート制限（レビュー S7、決定 037）。上限を超えたら 429 を返し、時間がたてば戻る。"""

import uuid
from datetime import timedelta

import freezegun
import pytest
from django.test import override_settings

from apps.core.testing import NOW, new_user
from apps.events.models import Log
from apps.events.services import events as ev_svc

# テストを速くするため、上限を小さくして確かめる（本番の値は settings.RATE_LIMITS）
SMALL = {"record": (3, 60), "write": (5, 60), "login": (2, 60), "export": (2, 3600), "stats": (4, 60), "all": (8, 60)}


@pytest.fixture
def event(user):
    return ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf")


def record(client, event):
    return client.post(f"/events/{event.id}/record/", {"log_id": str(uuid.uuid4())})


@override_settings(RATE_LIMITS=SMALL)
def test_記録が上限を超えたら_429_を返して記録しない(client_in, event):
    assert [record(client_in, event).status_code for _ in range(3)] == [200, 200, 200]

    r = record(client_in, event)

    assert r.status_code == 429 and Log.objects.count() == 3
    assert "操作が多すぎます" in r.content.decode()
    assert 1 <= int(r["Retry-After"]) <= 60


@override_settings(RATE_LIMITS=SMALL)
def test_時間がたてば_また記録できる(client_in, event):
    for _ in range(4):
        record(client_in, event)

    with freezegun.freeze_time(NOW + timedelta(seconds=61)):
        assert record(client_in, event).status_code == 200


@override_settings(RATE_LIMITS=SMALL)
def test_上限は人ごとに数える(client, user, event):
    client.force_login(user)
    for _ in range(4):
        record(client, event)

    other = new_user(email="b@example.com")
    theirs = ev_svc.create_event(other, name="散髪", emoji="✂️", color="grape")
    client.force_login(other)
    assert record(client, theirs).status_code == 200


@override_settings(RATE_LIMITS=SMALL)
def test_記録以外の書き込みにも上限がある(client_in):
    posts = [client_in.post("/categories/", {"action": "create", "name": f"c{i}"}).status_code for i in range(6)]
    assert posts == [200, 200, 200, 200, 200, 429]


@override_settings(RATE_LIMITS=SMALL)
def test_見るだけの操作は_全体の上限まで使える(client_in):
    gets = [client_in.get("/grid/").status_code for _ in range(9)]
    assert gets == [200] * 8 + [429]


@override_settings(RATE_LIMITS=SMALL)
def test_ログインの入口は_接続元ごとに数える(client, db):
    def start(ip):
        return client.get("/accounts/google/login/", HTTP_X_FORWARDED_FOR=ip).status_code

    assert [start("203.0.113.7") for _ in range(3)] == [200, 200, 429]
    assert start("203.0.113.8") == 200


@override_settings(RATE_LIMITS=SMALL)
def test_接続元は_偽装できない末尾の値で見分ける(client, db):
    """X-Forwarded-For の先頭は送る側が自由に書ける。Cloud Run が末尾に足す値だけを信用する。"""
    codes = [
        client.get("/accounts/google/login/", HTTP_X_FORWARDED_FOR=f"10.0.0.{i}, 203.0.113.7").status_code
        for i in range(3)
    ]
    assert codes == [200, 200, 429]


@override_settings(RATE_LIMITS=SMALL)
def test_書き出しは_1時間あたりの回数に上限がある(client_in):
    assert [client_in.post("/export/").status_code for _ in range(3)] == [200, 200, 429]

    with freezegun.freeze_time(NOW + timedelta(minutes=61)):
        assert client_in.post("/export/").status_code == 200


def test_ふつうの使い方では_本番の上限に当たらない(client_in, event):
    assert all(record(client_in, event).status_code == 200 for _ in range(30))
    assert client_in.get("/").status_code == 200


@override_settings(RATE_LIMITS=SMALL)
def test_集計の重い画面は_全体より厳しい上限で数える(client_in, event):
    """ふりかえりとイベント詳細は、そのたびに記録を集計する（セキュリティの見直し 2026-10-15）。"""
    urls = ["/review/", f"/events/{event.id}/", "/review/", f"/events/{event.id}/"]
    assert [client_in.get(u).status_code for u in urls] == [200, 200, 200, 200]
    assert client_in.get("/review/").status_code == 429
    assert client_in.get("/").status_code == 200  # ほかの画面は、全体の上限までは使える


@override_settings(RATE_LIMITS=SMALL)
def test_実績の一覧も_集計の重い画面として数える(client_in):
    assert [client_in.get("/achievements/").status_code for _ in range(4)] == [200] * 4
    assert client_in.get("/achievements/").status_code == 429
