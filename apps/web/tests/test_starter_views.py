"""はじめて使うときのテンプレートの画面（SPEC 3.6、決定 042）。"""

from apps.events.models import Event
from apps.events.services import events as ev_svc


def test_イベントが1つもないホームには_テンプレートの一覧が出る(client_in):
    body = client_in.get("/").content.decode()
    assert "まずは、よくあるものから選んでみましょう" in body
    assert 'name="starter"' in body and 'value="sheets"' in body and "自分で作る" in body


def test_イベントがあるホームには_テンプレートの一覧を出さない(client_in, event):
    assert 'name="starter"' not in client_in.get("/").content.decode()


def test_テンプレートを選んで追加すると_ホームに並ぶ(client_in):
    r = client_in.post("/starters/", {"starter": ["sheets", "haircut"]}, HTTP_HX_REQUEST="true")

    assert r.status_code == 204 and "yl:changed" in r["HX-Trigger"]
    body = client_in.get("/").content.decode()
    assert "シーツ交換" in body and "美容院" in body and 'name="starter"' not in body


def test_何も選ばずに追加しようとすると_知らせる(client_in):
    r = client_in.post("/starters/", {}, HTTP_HX_REQUEST="true")
    assert r.status_code == 200 and "1つ以上" in r.content.decode() and not Event.objects.exists()


def test_メニューから_あとでもテンプレートを開ける(client_in, user):
    assert "/starters/" in client_in.get("/menu/").content.decode()
    ev_svc.create_event(user, name="美容院", emoji="💇", color="pink")

    body = client_in.get("/starters/").content.decode()

    assert 'value="sheets"' in body and "追加済み" in body


def test_テンプレートの一覧は_組ごとに見出しをつけて出す(client_in):
    body = client_in.get("/").content.decode()
    for name in ("家のこと", "身だしなみ", "からだ", "人づきあい", "楽しみ"):
        assert f"<h3>{name}" in body
