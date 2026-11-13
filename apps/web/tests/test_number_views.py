"""数字の記録の画面（決定 074）。イベントの設定、数字を聞くシート、履歴、詳細の統計。"""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from apps.core.testing import TODAY
from apps.events.models import Event, Log
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.logs import When

FORM = {"name": "ランニング", "emoji": "🏃", "color": "leaf", "streak_unit": "day"}


@pytest.fixture
def run(user):
    return ev_svc.create_event(user, name="ランニング", emoji="🏃", color="leaf", number_kind="sum", number_unit="km")


@pytest.fixture
def weight(user):
    return ev_svc.create_event(user, name="体重", emoji="⚖️", color="sky", number_kind="trend", number_unit="kg")


def record(user, event, value, days_ago=0):
    return log_svc.record(user, event.id, uuid.uuid7(), When(date=TODAY - timedelta(days_ago)), value=value).log


def html(response) -> str:
    return response.content.decode()


# --- イベントの設定 -----------------------------------------------------------


def test_イベントのシートに_数字の記録の欄があり_はじめは_なし(client_in):
    page = html(client_in.get("/events/new/"))

    assert "数字の記録" in page
    assert 'name="number_kind" value="none" checked' in page
    assert 'name="number_unit"' in page


def test_数字の見せ方と単位を決めて_イベントを作れる(client_in):
    r = client_in.post("/events/new/", {**FORM, "number_kind": "sum", "number_unit": "km"}, HTTP_HX_REQUEST="true")

    assert r.status_code == 204
    event = Event.objects.get()
    assert (event.number_kind, event.number_unit) == ("sum", "km")


def test_編集のシートには_いまの設定が入っていて_変えられる(client_in, run):
    page = html(client_in.get(f"/events/{run.id}/edit/"))
    assert 'name="number_kind" value="sum" checked' in page
    assert 'name="number_unit" value="km"' in page

    r = client_in.post(f"/events/{run.id}/edit/", {**FORM, "number_kind": "trend", "number_unit": "分"})

    run.refresh_from_db()
    assert (r.status_code, run.number_kind, run.number_unit) == (204, "trend", "分")


def test_数字の欄がない古い画面から保存しても_数字の設定は消えない(client_in, run):
    client_in.post(f"/events/{run.id}/edit/", FORM)

    run.refresh_from_db()
    assert (run.number_kind, run.number_unit) == ("sum", "km")


def test_単位が長すぎれば_シートに誤りを出して_入力を残す(client_in):
    r = client_in.post(
        "/events/new/", {**FORM, "number_kind": "sum", "number_unit": "キロメートルくらい"}, HTTP_HX_REQUEST="true"
    )

    page = html(r)
    assert "単位は8文字まで" in page
    assert 'name="number_kind" value="sum" checked' in page and 'value="キロメートルくらい"' in page
    assert Event.objects.count() == 0


# --- 記録：数字を聞くシート ------------------------------------------------------


def test_数字を記録するイベントのタイルだけ_押すと数字を聞くシートを開く(client_in, run, event):
    page = html(client_in.get("/"))

    assert page.count("data-number-url=") == 1
    assert f'data-number-url="/events/{run.id}/record-sheet/?compact=1"' in page


def test_数字を聞くシートは_数字の欄が先で_日付とメモは畳んである(client_in, run):
    page = html(client_in.get(f"/events/{run.id}/record-sheet/?compact=1"))

    assert '<label for="recValue">数字（km）</label>' in page
    assert 'inputmode="decimal"' in page
    assert "<summary>日付やメモも入れる</summary>" in page
    assert page.index('id="recValue"') < page.index("<summary>")
    assert "空のままでも記録できます" in page
    assert "履歴・統計を見る" not in page  # 小さなシートにする


def test_数字の欄には_前回の数字を入れておく(client_in, user, run):
    record(user, run, "5.20", days_ago=1)

    page = html(client_in.get(f"/events/{run.id}/record-sheet/?compact=1"))

    assert 'name="value" inputmode="decimal" autocomplete="off" maxlength="16" value="5.2"' in page
    assert "前回の数字を入れてあります" in page


def test_単位がなければ_欄の名前は_数字_だけ(client_in, user):
    event = ev_svc.create_event(user, name="腕立て", emoji="💪", color="sun", number_kind="sum")

    assert '<label for="recValue">数字</label>' in html(client_in.get(f"/events/{event.id}/record-sheet/"))


def test_長押しのシートにも数字の欄があり_日付とメモは畳まない(client_in, run):
    page = html(client_in.get(f"/events/{run.id}/record-sheet/"))

    assert 'id="recValue"' in page and "<summary>" not in page and "履歴・統計を見る" in page


def test_数字を記録しないイベントのシートには_数字の欄がない(client_in, event):
    page = html(client_in.get(f"/events/{event.id}/record-sheet/?compact=1"))

    assert 'id="recValue"' not in page and "<summary>" not in page


def test_シートから_数字を付けて記録できる(client_in, run):
    r = client_in.post(
        f"/events/{run.id}/record-sheet/",
        {"log_id": str(uuid.uuid4()), "when": "now", "value": "５．２", "compact": "1"},
    )

    assert r.status_code == 204
    assert Log.objects.get().value == Decimal("5.2")


def test_数字が空のままでも記録できる(client_in, run):
    r = client_in.post(f"/events/{run.id}/record-sheet/", {"log_id": str(uuid.uuid4()), "when": "now", "value": ""})

    assert (r.status_code, Log.objects.get().value) == (204, None)


def test_数字として読めなければ_同じ小さなシートに誤りを出して_入力を残す(client_in, run):
    r = client_in.post(
        f"/events/{run.id}/record-sheet/",
        {"log_id": str(uuid.uuid4()), "when": "now", "value": "たくさん", "compact": "1"},
    )

    page = html(r)
    assert "数字は 0〜999,999,999 の範囲で" in page
    assert 'value="たくさん"' in page and "<summary>" in page and 'name="compact" value="1"' in page
    assert Log.objects.count() == 0


def test_タップの受け口でも_数字を受け取る(client_in, run):
    r = client_in.post(f"/events/{run.id}/record/", {"log_id": str(uuid.uuid4()), "value": "3"})

    assert r.json()["created"] is True
    assert Log.objects.get().value == Decimal("3")


def test_古い画面からの1タップは_数字なしで記録される(client_in, run):
    """開いたままの画面（古いスクリプト）は、数字を聞かずに記録を送る。あとから編集で数字を足せる。"""
    r = client_in.post(f"/events/{run.id}/record/", {"log_id": str(uuid.uuid4())})

    assert (r.status_code, Log.objects.get().value) == (200, None)


def test_タップの受け口は_数字として読めなければ422(client_in, run):
    r = client_in.post(f"/events/{run.id}/record/", {"log_id": str(uuid.uuid4()), "value": "x"})

    assert (r.status_code, Log.objects.count()) == (422, 0)


# --- 編集と履歴 -----------------------------------------------------------------


def test_記録の編集で_数字を直せる(client_in, user, run):
    log = record(user, run, "5")

    page = html(client_in.get(f"/logs/{log.id}/edit/"))
    assert 'value="5"' in page and "前回の数字を入れてあります" not in page and "<summary>" not in page

    r = client_in.post(f"/logs/{log.id}/edit/", {"when": "pick", "date": TODAY.isoformat(), "value": "7.5"})

    log.refresh_from_db()
    assert (r.status_code, log.value) == (204, Decimal("7.5"))


def test_数字のない記録の編集では_前回の数字を入れない(client_in, user, run):
    record(user, run, "5", days_ago=1)
    log = record(user, run, "")

    assert 'maxlength="16" value=""' in html(client_in.get(f"/logs/{log.id}/edit/"))


def test_履歴に_数字と単位を出す(client_in, user, run):
    record(user, run, "1200.5")
    record(user, run, "", days_ago=1)

    page = html(client_in.get(f"/events/{run.id}/"))

    assert '<b class="num">1,200.5<small>km</small></b>' in page
    assert page.count('<b class="num">') == 1
    assert page.count("メモなし") == 1  # 数字もメモもない記録だけ


# --- 詳細の統計 -----------------------------------------------------------------


def test_合計で見るイベントの詳細に_今月_今年_これまでの合計と_月ごとの棒が出る(client_in, user, run):
    record(user, run, "5")
    record(user, run, "3.5", days_ago=9)
    record(user, run, "10", days_ago=10)

    page = html(client_in.get(f"/events/{run.id}/"))

    assert "数字の合計" in page
    for label, value in (("今月", "8.5"), ("今年", "18.5"), ("これまで", "18.5")):
        assert f'<div class="k">{label}</div><div class="v">{value}<small>km</small></div>' in page
    assert 'aria-label="2026年10月：8.5km"' in page and 'aria-label="2026年9月：10km"' in page
    assert page.count('class="wbar nb') == 12


def test_推移で見るイベントの詳細に_最新_平均_最小_最大と_折れ線が出る(client_in, user, weight):
    record(user, weight, "64", days_ago=4)
    record(user, weight, "63", days_ago=2)
    record(user, weight, "62.4")

    page = html(client_in.get(f"/events/{weight.id}/"))

    assert "数字の推移" in page
    for label, value in (("最新", "62.4"), ("平均", "63.13"), ("最小", "62.4"), ("最大", "64")):
        assert f'<div class="k">{label}</div><div class="v">{value}<small>kg</small></div>' in page
    assert "前回より −0.6kg" in page
    assert "<polyline" in page and page.count("<circle") == 3
    assert "<caption>数字の推移</caption>" in page and "<td>10月10日</td><td>62.4kg</td>" in page


def test_数字が1つだけなら_折れ線の代わりに案内を出す(client_in, user, weight):
    record(user, weight, "62")

    page = html(client_in.get(f"/events/{weight.id}/"))

    assert "<polyline" not in page and "数字が2つたまると、グラフが出ます" in page


@pytest.mark.parametrize(("kind", "word"), [("sum", "合計"), ("trend", "推移")])
def test_数字の記録がまだなければ_案内だけを出す(client_in, user, kind, word):
    event = ev_svc.create_event(user, name="読書", emoji="📚", color="sky", number_kind=kind, number_unit="ページ")

    page = html(client_in.get(f"/events/{event.id}/"))

    assert f"数字を付けて記録すると、ここに{word}が出ます" in page
    assert "<polyline" not in page and 'class="wbar' not in page


def test_数字を記録しないイベントの詳細には_数字のカードがない(client_in, user, event):
    log_svc.record(user, event.id, uuid.uuid7())

    page = html(client_in.get(f"/events/{event.id}/"))

    assert "数字の合計" not in page and "数字の推移" not in page and '<b class="num">' not in page
