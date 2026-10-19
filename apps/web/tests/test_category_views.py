"""カテゴリの編集（一覧は読むだけ、行を押すと編集画面）。"""

import json

from apps.core.testing import new_user
from apps.events.services import events as ev_svc


def toast_of(r):
    return json.loads(r["HX-Trigger"]).get("yl:toast", {}).get("message")


def test_一覧は読むだけで_行を押すとそのカテゴリの編集画面が開く(client_in, user):
    house = ev_svc.create_category(user, "家のこと", "🏠")
    ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", category_id=house.id)
    ev_svc.create_category(user, "からだ")

    body = client_in.get("/categories/").content.decode()

    assert f'hx-get="/categories/{house.id}/"' in body and "1件" in body and "🛏️" in body
    assert "まだイベントはありません" in body
    assert 'name="name"' not in body  # 一覧には入力欄を出さない
    assert 'hx-get="/categories/new/"' in body and "カテゴリを追加" in body


def test_編集画面には_名前と絵文字と_中のイベントと_削除がある(client_in, user):
    house = ev_svc.create_category(user, "家のこと", "🏠")
    ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", category_id=house.id)

    body = client_in.get(f"/categories/{house.id}/").content.decode()

    assert 'name="name" value="家のこと"' in body and 'value="🏠" checked' in body
    assert "シーツ交換" in body and "このカテゴリを削除" in body
    assert "hx-confirm" not in body  # ブラウザの確認画面は使わない


def test_編集画面で保存すると_一覧に戻り_保存しましたと知らせる(client_in, user):
    house = ev_svc.create_category(user, "家のこと")
    r = client_in.post(
        "/categories/", {"action": "rename", "id": house.id, "name": "おうち", "emoji": "", "emoji_custom": "🏠"}
    )
    assert toast_of(r) == "保存しました" and 'class="catlist"' in r.content.decode()
    house.refresh_from_db()
    assert (house.name, house.emoji) == ("おうち", "🏠")


def test_追加の画面から作ると_一覧に戻り_追加しましたと知らせる(client_in, user):
    assert "カテゴリを追加" in client_in.get("/categories/new/").content.decode()
    r = client_in.post("/categories/", {"action": "create", "name": "楽しみ", "emoji": ""})
    assert toast_of(r) == "追加しました" and [c.name for c in ev_svc.list_categories(user)] == ["楽しみ"]


def test_編集画面での誤りは_同じ画面で知らせる(client_in, user):
    ev_svc.create_category(user, "家のこと")
    other = ev_svc.create_category(user, "からだ")
    r = client_in.post("/categories/", {"action": "rename", "id": other.id, "name": "家のこと", "form": "1"})
    body = r.content.decode()
    assert (
        "同じ名前のカテゴリがあります" in body
        and 'name="name" value="家のこと"' in body
        and 'class="catlist"' not in body
    )


def test_削除は_アプリの中で確かめてから消す(client_in, user):
    house = ev_svc.create_category(user, "家のこと")
    ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", category_id=house.id)

    body = client_in.get(f"/categories/{house.id}/?confirm=1").content.decode()
    assert "「家のこと」を削除しますか" in body and "1件のイベントは「カテゴリなし」になります" in body

    r = client_in.post("/categories/", {"action": "delete", "id": house.id})
    assert toast_of(r) == "削除しました" and not ev_svc.list_categories(user).exists()


def test_ほかの人のカテゴリの編集画面は_開けない(client_in):
    other = new_user(email="b@example.com")
    theirs = ev_svc.create_category(other, "ひみつ")
    assert client_in.get(f"/categories/{theirs.id}/").status_code == 404
