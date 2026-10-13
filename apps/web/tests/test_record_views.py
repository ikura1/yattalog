"""記録の画面（タップ、取り消し、長押しシート、編集）。"""

import json
import uuid

import pytest

from apps.events.models import Log
from apps.events.services import logs as log_svc


def test_同じIDで2回記録しても1件(client_in, event):
    lid = str(uuid.uuid4())
    r1 = client_in.post(f"/events/{event.id}/record/", {"log_id": lid})
    r2 = client_in.post(f"/events/{event.id}/record/", {"log_id": lid})
    assert (r1.json()["created"], r2.json()["created"]) == (True, False)
    assert Log.objects.count() == 1 and "さっき" in r1.json()["tile_html"]


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


# --- 長押しシートから、さっきの記録を取り消す（決定 054） ---


def test_記録した直後の長押しシートには_さっきの記録を取り消すボタンが出る(client_in, user, event):
    lid = uuid.uuid4()
    log_svc.record(user, event.id, lid)

    body = client_in.get(f"/events/{event.id}/record-sheet/").content.decode()

    assert "さっきの記録を取り消す" in body and f'hx-post="/logs/{lid}/delete/"' in body


def test_しばらくたった記録や_記録がないときは_取り消すボタンを出さない(client_in, user, event):
    from datetime import timedelta

    from apps.core.testing import NOW

    assert "さっきの記録を取り消す" not in client_in.get(f"/events/{event.id}/record-sheet/").content.decode()

    result = log_svc.record(user, event.id, uuid.uuid4())
    Log.objects.filter(pk=result.log.pk).update(created_at=NOW - timedelta(minutes=30))

    assert "さっきの記録を取り消す" not in client_in.get(f"/events/{event.id}/record-sheet/").content.decode()


def test_シートから取り消すと_記録が消えて_取り消しましたと知らせる(client_in, user, event):
    lid = uuid.uuid4()
    log_svc.record(user, event.id, lid)

    r = client_in.post(f"/logs/{lid}/delete/", {"undo": "1"}, HTTP_HX_REQUEST="true")

    assert r.status_code == 204 and not Log.objects.exists()
    assert json.loads(r["HX-Trigger"])["yl:toast"]["message"] == "取り消しました"


def test_シートを閉じる合図より先に_知らせの合図を送る(client_in, user, event):
    """シートを閉じると、合図を出したボタンが画面から消える。その後に送った合図は、どこにも届かない。

    知らせ（トースト）を閉じる合図より後に送っていたので、シートからの操作では、知らせが出ていなかった。
    """
    lid = uuid.uuid4()
    log_svc.record(user, event.id, lid)

    r = client_in.post(f"/logs/{lid}/delete/", {"undo": "1"}, HTTP_HX_REQUEST="true")

    order = list(json.loads(r["HX-Trigger"]))
    assert order.index("yl:toast") < order.index("yl:close-sheet")
    assert order.index("yl:changed") < order.index("yl:close-sheet")
