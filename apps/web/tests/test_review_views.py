"""ふりかえりの画面（1年の草、決定 058）。"""

import uuid
from datetime import timedelta

from apps.core.testing import TODAY, new_user
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.logs import When


def record(user, event, days_ago=0):
    when = When(date=TODAY - timedelta(days_ago)) if days_ago else None
    log_svc.record(user, event.id, uuid.uuid4(), when)


def test_メニューから_ふりかえりを開ける(client_in):
    assert 'href="/review/"' in client_in.get("/menu/").content.decode()


def test_ふりかえりには_12か月の草と_やった回数と日数が出る(client_in, user, event):
    record(user, event)
    record(user, event, 30)

    body = client_in.get("/review/").content.decode()

    assert "この1年で" in body and ">2</b> 回" in body and ">2</b> 日" in body
    assert '<span class="hm-m">11月</span>' in body and '<span class="hm-m">1月</span>' in body
    assert 'aria-label="10月10日（土）：1回"' in body


def test_はじめは今日の記録を出し_日付を押すとその日の記録を出す(client_in, user, event):
    water = ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf")
    record(user, event)
    record(user, water, 3)

    today = client_in.get("/review/").content.decode()
    picked = client_in.get("/review/?day=2026-10-07").content.decode()

    assert "10月10日（土）" in today and "シーツ交換" in today.split('id="reviewDay"')[1]
    assert "水やり" in picked.split('id="reviewDay"')[1] and "シーツ交換" not in picked.split('id="reviewDay"')[1]


def test_イベントで絞ると_そのイベントの記録だけを出す(client_in, user, event):
    water = ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf")
    record(user, event)
    record(user, water)

    body = client_in.get(f"/review/?event={water.id}").content.decode()

    assert ">1</b> 回" in body
    assert f'href="?event={water.id}&amp;day=2026-10-10" aria-current="true"' in body
    assert "シーツ交換" not in body.split('id="reviewDay"')[1]
    assert 'class="review c-leaf"' in body  # やった日は、そのイベントの色で塗る


def test_ほかの人のイベントでは_絞れない(client_in):
    other = new_user(email="b@example.com")
    theirs = ev_svc.create_event(other, name="ひみつ", emoji="🤫", color="pink")
    assert client_in.get(f"/review/?event={theirs.id}").status_code == 404
    assert client_in.get("/review/?event=not-a-uuid").status_code == 404


def test_読めない日付や_先の日付は_今日として扱う(client_in, user, event):
    record(user, event)
    for day in ("2026-13-40", "2026-12-01", "x"):
        body = client_in.get(f"/review/?day={day}").content.decode()
        assert "シーツ交換" in body.split('id="reviewDay"')[1]


def test_画面の中の切り替えでは_中身だけを返す(client_in):
    body = client_in.get("/review/?day=2026-10-09", HTTP_HX_REQUEST="true").content.decode()
    assert "<html" not in body and 'id="reviewDay"' in body


def test_ログインしていないと_ログイン画面へ(client):
    assert client.get("/review/")["Location"].startswith("/login/")


def test_ふりかえりには_よくやる曜日が出て_絞ったイベントにも効く(client_in, user, event):
    water = ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf")
    for days in (0, 7, 14):  # 2026-10-10 は土曜
        record(user, event, days)
    record(user, water, 3)

    body = client_in.get("/review/").content.decode()
    only_water = client_in.get(f"/review/?event={water.id}").content.decode()

    assert "よくやる曜日" in body and "よくやるのは 土曜" in body
    assert 'class="wbar peak" aria-label="土曜：3回"' in body and 'aria-label="水曜：1回"' in body
    assert "記録が増えると、よくやる曜日がわかります" in only_water


def test_ふりかえりの画面は_style_属性を使わない(client_in, user, event):
    """CSP で style 属性は止まる（style-src に unsafe-inline がない）。高さや色は、クラスか SVG の属性で渡す。"""
    record(user, event)
    assert "style=" not in client_in.get("/review/").content.decode()


def test_ふりかえりには_よくやる時間帯も出る(client_in, user, event):
    from datetime import time

    for hh in (7, 8, 21):
        log_svc.record(user, event.id, uuid.uuid4(), When(date=TODAY - timedelta(1), time=time(hh)))

    body = client_in.get("/review/").content.decode()

    assert "よくやる時間帯" in body and "よくやるのは 朝" in body
    assert 'class="wbar peak" aria-label="朝：2回"' in body and 'aria-label="夜：1回"' in body
    assert "時刻つきの記録だけで数えます" in body
