"""イベントとカテゴリの画面（追加・編集、アイコン、絵文字、タブ、詳細）。"""

import uuid
from datetime import date

import pytest

from apps.events.models import Category, Event
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.logs import When


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


def test_おすすめのアイコンはすべて絵文字として通る(user):
    from apps.web.views import EMOJIS

    for emoji in EMOJIS:
        assert ev_svc.create_event(user, name="x", emoji=emoji, color="sky").emoji == emoji


def test_入力欄に絵文字を入れると_おすすめの選択より優先される(client_in):
    r = client_in.post(
        "/events/new/",
        {"name": "ぎょうざ", "emoji": "✂️", "emoji_custom": "🥟", "color": "sky", "streak_unit": "day"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204 and Event.objects.get(name="ぎょうざ").emoji == "🥟"


def test_入力欄だけでアイコンを決められる(client_in):
    r = client_in.post(
        "/events/new/",
        {"name": "ぎょうざ", "emoji_custom": "🥟", "color": "sky", "streak_unit": "day"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204 and Event.objects.get(name="ぎょうざ").emoji == "🥟"


def test_入力欄が絵文字でなければ_フォームにエラーを出して入力を残す(client_in):
    r = client_in.post(
        "/events/new/",
        {"name": "ぎょうざ", "emoji": "✂️", "emoji_custom": "ぎょ", "color": "sky", "streak_unit": "day"},
        HTTP_HX_REQUEST="true",
    )
    body = r.content.decode()
    assert r.status_code == 200 and not Event.objects.exists()
    assert "絵文字を1つ" in body and 'name="emoji_custom" value="ぎょ"' in body


def test_編集シートでは_おすすめにないアイコンが入力欄に入っている(client_in, user):
    e = ev_svc.create_event(user, name="ぎょうざ", emoji="🥟", color="sky")
    body = client_in.get(f"/events/{e.id}/edit/").content.decode()
    recommended = body.split('class="emojis"')[1].split("</div>")[0]
    assert 'name="emoji_custom" value="🥟"' in body and " checked" not in recommended


def test_編集シートでは_おすすめにあるアイコンは一覧で選ばれ_入力欄は空(client_in, event):
    body = client_in.get(f"/events/{event.id}/edit/").content.decode()
    assert 'name="emoji_custom" value=""' in body and 'value="🛏️" checked' in body


def test_編集で入力欄の絵文字に変えられる(client_in, event):
    r = client_in.post(
        f"/events/{event.id}/edit/",
        {"name": "シーツ交換", "emoji_custom": "🧸", "color": "sky", "streak_unit": "week"},
        HTTP_HX_REQUEST="true",
    )
    event.refresh_from_db()
    assert r.status_code == 204 and event.emoji == "🧸"


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


def test_カテゴリを絵文字つきで作ると_タブとイベントのシートに絵文字が出る(client_in, user):
    r = client_in.post("/categories/", {"action": "create", "name": "家事", "emoji": "🧹"})
    assert r.status_code == 200 and Category.objects.get(name="家事").emoji == "🧹"
    assert "🧹</span>家事" in client_in.get("/").content.decode()
    assert "🧹</span>家事" in client_in.get("/events/new/").content.decode()


def test_絵文字なしのカテゴリは_名前だけが出る(client_in, user):
    ev_svc.create_category(user, "家事")
    assert 'class="cat-emo"' not in client_in.get("/").content.decode()


def test_カテゴリの一覧で絵文字を変えたり外したりできる(client_in, user):
    house = ev_svc.create_category(user, "家事", emoji="🧹")
    client_in.post("/categories/", {"action": "rename", "id": str(house.id), "name": "家事", "emoji": "🧺"})
    house.refresh_from_db()
    assert house.emoji == "🧺"

    client_in.post("/categories/", {"action": "rename", "id": str(house.id), "name": "家事", "emoji": ""})
    house.refresh_from_db()
    assert house.emoji == ""


def test_カテゴリの絵文字が正しくなければ_エラーを出して保存しない(client_in, user):
    r = client_in.post("/categories/", {"action": "create", "name": "家事", "emoji": "そうじ"})
    assert "絵文字を1つ" in r.content.decode() and not Category.objects.exists()
    assert "HX-Trigger" not in r


def test_カテゴリがあって_入っていないイベントもあれば_カテゴリなしのタブが件数つきで出る(client_in, user, event):
    house = ev_svc.create_category(user, "家事")
    ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf", category_id=house.id)
    ev_svc.create_event(user, name="散髪", emoji="✂️", color="grape")

    body = client_in.get("/").content.decode()

    assert 'data-tab="none"' in body and 'カテゴリなし<span class="n">2</span>' in body
    assert body.index('data-tab="none"') > body.index(f'data-tab="{house.id}"')


def test_カテゴリが1つもなければ_カテゴリなしのタブは出さない(client_in, event):
    assert 'data-tab="none"' not in client_in.get("/").content.decode()


def test_どのイベントもカテゴリに入っていれば_カテゴリなしのタブは出さない(client_in, user):
    house = ev_svc.create_category(user, "家事")
    ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf", category_id=house.id)

    assert 'data-tab="none"' not in client_in.get("/").content.decode()


def test_カテゴリなしのタブから追加するときは_カテゴリの欄で_なし_が選ばれている(client_in, user):
    ev_svc.create_category(user, "家事")

    body = client_in.get("/events/new/?category=none").content.decode()

    assert '<input type="radio" name="category" value="" checked>' in body


def test_詳細画面では_2か月前と一緒に_正確な日数と日付も出る(client_in, user):
    from datetime import timedelta

    from apps.core.testing import TODAY

    e = ev_svc.create_event(user, name="散髪", emoji="✂️", color="grape", last_done=TODAY - timedelta(63))

    body = client_in.get(f"/events/{e.id}/").content.decode()

    assert "2<small>か月前</small>" in body and "前回 8月8日（63日前）" in body


def test_詳細の統計に_最高連続を出す_単位がなしのイベントには出さない(client_in, user, event):
    for d in (date(2026, 9, 28), date(2026, 10, 5)):
        log_svc.record(user, event.id, uuid.uuid4(), When(date=d))
    dentist = ev_svc.create_event(user, name="歯医者", emoji="🦷", color="pink", streak_unit="none")

    body = client_in.get(f"/events/{event.id}/").content.decode()
    assert "最高連続" in body and "2週連続" in body
    assert "最高連続" not in client_in.get(f"/events/{dentist.id}/").content.decode()


def test_詳細に_はじめて記録した日と_どれくらい前かを出す(client_in, user, event):
    log_svc.record(user, event.id, uuid.uuid4(), When(date=date(2025, 8, 3)))
    log_svc.record(user, event.id, uuid.uuid4())

    body = client_in.get(f"/events/{event.id}/").content.decode()

    assert "はじめての記録 2025年8月3日（1年2か月前）" in body
