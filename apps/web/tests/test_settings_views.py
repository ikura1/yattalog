"""設定（週の始まり、押したときの震え、見た目、タイムゾーン。決定 066）。"""

import json

from apps.spaces.services import personal_space


def trig(r):
    return json.loads(r["HX-Trigger"])


def post(client, **over):
    data = {"week_start": "mon", "haptics": "1", "theme": "auto", "timezone": "Asia/Tokyo", **over}
    return client.post("/settings/", data)


def test_メニューの設定の組から_設定を開ける(client_in):
    body = client_in.get("/menu/").content.decode()
    assert '<h3 class="menu-h">設定</h3>' in body and 'hx-get="/settings/"' in body


def test_設定の画面には_いまの値が選ばれている(client_in, user):
    body = client_in.get("/settings/").content.decode()
    assert 'name="week_start" value="mon" checked' in body
    assert 'name="theme" value="auto" checked' in body
    assert 'name="haptics" value="1" checked' in body
    assert '<option value="Asia/Tokyo" selected>' in body


def test_保存すると_知らせて_見た目と震えをその場で変える(client_in, user):
    r = post(client_in, theme="dark", haptics="")
    user.refresh_from_db()
    assert (user.theme, user.haptics) == ("dark", False)
    t = trig(r)
    assert t["yl:toast"]["message"] == "保存しました" and t["yl:prefs"] == {"theme": "dark", "haptics": False}


def test_週の始まりを変えると_ホームも並べ直す(client_in, user):
    t = trig(post(client_in, week_start="sun"))
    assert personal_space(user).week_start == "sun" and t.get("yl:changed") is True


def test_タイムゾーンを自分で選べる(client_in, user):
    post(client_in, timezone="America/New_York")
    user.refresh_from_db()
    assert user.timezone == "America/New_York"


def test_正しくない値は_保存せずに知らせる(client_in, user):
    for bad in ({"theme": "pink"}, {"week_start": "wed"}, {"timezone": "Mars/Base"}):
        r = post(client_in, **bad)
        assert r.status_code == 200 and 'role="alert"' in r.content.decode()
    user.refresh_from_db()
    assert (user.theme, user.timezone) == ("auto", "Asia/Tokyo") and personal_space(user).week_start == "mon"


def test_見た目を選んでいれば_ページ全体に印を付ける_端末に合わせるなら付けない(client_in, user):
    assert "data-theme=" not in client_in.get("/").content.decode()
    user.theme, user.haptics = "dark", False
    user.save()
    body = client_in.get("/").content.decode()
    assert '<html lang="ja" data-theme="dark">' in body and 'data-haptics="0"' in body
