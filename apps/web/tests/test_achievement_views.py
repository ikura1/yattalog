"""実績バッジの画面（SPEC 3.10、決定 020・063）。解除したら、その操作の知らせに添えて伝える。"""

import json
import uuid
from datetime import timedelta

from apps.core.testing import TODAY
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.logs import When


def tap(client, event):
    return client.post(f"/events/{event.id}/record/", {"log_id": str(uuid.uuid4())}).json()


def toast_of(response):
    return json.loads(response["HX-Trigger"])["yl:toast"]["message"]


def test_タップで記録して実績を解除したら_知らせの文言を返す(client_in, event):
    assert tap(client_in, event)["achievement"] == "🏅 実績解除：はじめの一歩"
    assert tap(client_in, event)["achievement"] == ""


def test_機能が入る前からの人は_最初の記録では知らせない(client_in, user, event):
    client_in.raise_request_exception = True
    user.achievements_synced = False
    user.save()
    assert tap(client_in, event)["achievement"] == ""


def test_シートから記録して解除したら_知らせに添える(client_in, event):
    r = client_in.post(f"/events/{event.id}/record-sheet/", {"log_id": str(uuid.uuid4())})
    assert toast_of(r) == "やった！ 記録しました　🏅 実績解除：はじめの一歩"


def test_記録を過去の日付に直すと_思い出した(client_in, user, event):
    log = log_svc.record(user, event.id, uuid.uuid4()).log
    client_in.post(f"/events/{event.id}/record-sheet/", {"log_id": str(uuid.uuid4())})  # はじめの一歩を先に済ませる
    past = (TODAY - timedelta(5)).isoformat()
    r = client_in.post(f"/logs/{log.id}/edit/", {"when": "pick", "date": past, "memo": ""})
    assert toast_of(r) == "記録を更新しました　🏅 実績解除：思い出した"


def test_イベントを10個作ると_コレクター(client_in, user):
    for i in range(9):
        ev_svc.create_event(user, name=f"e{i}", emoji="⭐", color="sky")
    r = client_in.post("/events/new/", {"name": "10個目", "emoji": "⭐", "color": "sky", "streak_unit": "none"})
    assert toast_of(r) == "追加しました　🏅 実績解除：コレクター"


def test_シェアしたと知らせると_シェアデビュー(client_in):
    assert client_in.post("/achievements/share/").json() == {"achievement": "🏅 実績解除：シェアデビュー"}
    assert client_in.post("/achievements/share/").json() == {"achievement": ""}
    assert client_in.get("/achievements/share/").status_code == 405


def test_ログインしていないと_実績は見られず_知らせも受け付けない(client):
    assert client.get("/achievements/")["Location"].startswith("/login/")
    assert client.post("/achievements/share/").status_code == 302


def test_メニューから_実績の一覧を開ける(client_in):
    assert 'hx-get="/achievements/"' in client_in.get("/menu/").content.decode()


def test_実績の一覧は_解除したものに日付_まだのものに条件を出す(client_in, user, event):
    log_svc.record(user, event.id, uuid.uuid4(), When(date=TODAY))
    tap(client_in, event)

    body = client_in.get("/achievements/").content.decode()

    assert "はじめの一歩" in body and "10月10日" in body  # 解除した日（利用者のタイムゾーン）
    assert "全部のイベントの合計で10回記録する" in body  # まだのものは、条件を出す
    assert "1 / 15" in body  # 解除した数
    assert "フォトログ" not in body
