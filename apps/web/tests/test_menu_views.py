"""メニュー（組ごとに分けて並べる）。アーカイブは別の画面に分ける。"""

import re

from apps.events.services import events as ev_svc


def test_メニューは_見る_整える_アプリ_サポート_アカウントの組に分けて並べる(client_in):
    body = client_in.get("/menu/").content.decode()
    heads = re.findall(r'<h3 class="menu-h">([^<]+)</h3>', body)
    assert heads == ["見る", "整える", "アプリ", "サポート", "アカウント"]
    account = body.split('<h3 class="menu-h">アカウント</h3>')[1]
    assert "データを書き出す" in account and "ログアウト" in account and "退会する" in account


def test_アーカイブは_件数だけを出し_別の画面で戻せる(client_in, user, event):
    ev_svc.set_archived(user, event.id, True)

    menu = client_in.get("/menu/").content.decode()
    assert 'hx-get="/archived/"' in menu and "アーカイブしたイベント" in menu and ">1<" in menu
    assert "戻す" not in menu

    sheet = client_in.get("/archived/").content.decode()
    assert "シーツ交換" in sheet and f'hx-post="/events/{event.id}/restore/"' in sheet and "← メニュー" in sheet


def test_アーカイブがなければ_そう出す(client_in):
    assert "アーカイブしたイベントはありません" in client_in.get("/archived/").content.decode()


def test_メニューの下には_いまの段階を出す(client_in):
    body = client_in.get("/menu/").content.decode()
    assert "β 版" in body and "α 版" not in body
