"""段階で選ぶ・チェックするの画面（決定 076）。イベントの設定、記録のシート、履歴、詳細のカード。"""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from apps.core.testing import TODAY
from apps.events.models import Event, Log
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.logs import When

FORM = {"name": "掃除", "emoji": "🧹", "color": "teal", "streak_unit": "day"}
ITEMS = ["床", "トイレ", "風呂", "キッチン"]


@pytest.fixture
def pain(user):
    return ev_svc.create_event(user, name="頭痛", emoji="🤕", color="grape", number_kind="scale")


@pytest.fixture
def clean(user):
    return ev_svc.create_event(user, name="掃除", emoji="🧹", color="teal", number_kind="check", check_items=ITEMS)


def record(user, event, days_ago=0, **kw):
    return log_svc.record(user, event.id, uuid.uuid7(), When(date=TODAY - timedelta(days_ago)), **kw).log


def html(response) -> str:
    return response.content.decode()


def sheet(client, event, compact=True):
    return html(client.get(f"/events/{event.id}/record-sheet/" + ("?compact=1" if compact else "")))


def post(client, event, **data):
    return client.post(
        f"/events/{event.id}/record-sheet/", {"log_id": str(uuid.uuid4()), "when": "now", "compact": "1", **data}
    )


# --- イベントの設定 -----------------------------------------------------------


def test_イベントのシートで_記録のしかたを5つから選べる(client_in):
    page = html(client_in.get("/events/new/"))

    assert '<legend class="lbl">記録のしかた</legend>' in page
    for kind in ("none", "sum", "trend", "scale", "check"):
        assert f'name="number_kind" value="{kind}"' in page
    assert 'name="number_kind" value="none" checked' in page
    assert '<textarea id="evItems" name="check_items"' in page


def test_段階で選ぶイベントを作れる(client_in):
    r = client_in.post("/events/new/", {**FORM, "number_kind": "scale"}, HTTP_HX_REQUEST="true")

    assert r.status_code == 204
    assert Event.objects.get().is_scale


def test_チェックする項目を_1行に1つ入れて_イベントを作れる(client_in):
    r = client_in.post(
        "/events/new/",
        {**FORM, "number_kind": "check", "check_items": "床\r\n トイレ \r\n\r\n風呂"},
        HTTP_HX_REQUEST="true",
    )

    event = Event.objects.get()
    assert (r.status_code, event.is_check, event.check_items) == (204, True, ["床", "トイレ", "風呂"])


def test_項目がなければ_シートに誤りを出して_入力を残す(client_in):
    r = client_in.post("/events/new/", {**FORM, "number_kind": "check", "check_items": ""}, HTTP_HX_REQUEST="true")

    page = html(r)
    assert "チェックする項目を1つ以上入れてください" in page
    assert 'name="number_kind" value="check" checked' in page
    assert Event.objects.count() == 0


def test_項目が長すぎれば_入れたものを欄に残す(client_in):
    r = client_in.post(
        "/events/new/",
        {**FORM, "number_kind": "check", "check_items": "床\nとても長い名前の掃除する場所"},
        HTTP_HX_REQUEST="true",
    )

    page = html(r)
    assert "項目は12文字までです" in page and "床\nとても長い名前の掃除する場所</textarea>" in page


def test_編集のシートには_いまの項目が1行に1つ入っている(client_in, clean):
    page = html(client_in.get(f"/events/{clean.id}/edit/"))

    assert 'name="number_kind" value="check" checked' in page
    assert "床\nトイレ\n風呂\nキッチン</textarea>" in page


def test_編集で項目を変えられる(client_in, clean):
    r = client_in.post(f"/events/{clean.id}/edit/", {**FORM, "number_kind": "check", "check_items": "床\n窓"})

    clean.refresh_from_db()
    assert (r.status_code, clean.check_items) == (204, ["床", "窓"])


def test_項目の欄がない古い画面から保存しても_項目は消えない(client_in, clean):
    r = client_in.post(f"/events/{clean.id}/edit/", {**FORM, "number_kind": "check"})

    clean.refresh_from_db()
    assert (r.status_code, clean.check_items) == (204, ITEMS)


# --- ホーム -------------------------------------------------------------------


def test_段階とチェックのイベントも_押すとシートを開く(client_in, pain, clean, event):
    page = html(client_in.get("/"))

    assert page.count("data-number-url=") == 2
    for e in (pain, clean):
        assert f'data-number-url="/events/{e.id}/record-sheet/?compact=1"' in page


# --- 段階で選ぶ ---------------------------------------------------------------


def test_段階のシートは_1から5のスライダーで_日付とメモは畳んである(client_in, pain):
    page = sheet(client_in, pain)

    assert '<label for="recScale">段階（1〜5）</label>' in page
    assert '<input type="range" id="recScale" name="value" min="1" max="5" step="1" value="3"' in page
    assert page.index('id="recScale"') < page.index("<summary>日付やメモも入れる</summary>")
    assert 'id="recValue"' not in page and "よく使う数字" not in page
    assert "keep_value" not in page


def test_段階の大きな表示は_スクリプトが動くまで隠しておく(client_in, pain):
    """開いたままの古いスクリプトでは動かない。動かない数字を見せない。"""
    assert "<output" in sheet(client_in, pain) and "data-scale-out hidden" in sheet(client_in, pain)


def test_スライダーは_前回の段階に合わせておく(client_in, user, pain):
    record(user, pain, 1, value="4")

    page = sheet(client_in, pain)

    assert 'step="1" value="4"' in page and "前回の段階に合わせてあります" in page


def test_スライダーで選んだ段階を付けて記録できる(client_in, pain):
    r = post(client_in, pain, value="5")

    assert (r.status_code, Log.objects.get().value) == (204, Decimal(5))


def test_段階として読めなければ_同じシートに誤りを出す(client_in, pain):
    page = html(post(client_in, pain, value="9"))

    assert "段階は 1〜5 で選んでください" in page and 'id="recScale"' in page
    assert Log.objects.count() == 0


def test_記録の編集で_段階を直せる(client_in, user, pain):
    log = record(user, pain, value="2")

    page = html(client_in.get(f"/logs/{log.id}/edit/"))
    assert 'step="1" value="2"' in page and "keep_value" not in page

    r = client_in.post(f"/logs/{log.id}/edit/", {"when": "pick", "date": TODAY.isoformat(), "value": "4"})
    log.refresh_from_db()
    assert (r.status_code, log.value) == (204, Decimal(4))


def test_段階のない記録の編集では_付けないままにできる(client_in, user, pain):
    """スライダーは空にできない。メモを直しただけで、段階が付かないようにする。"""
    log = record(user, pain)

    page = html(client_in.get(f"/logs/{log.id}/edit/"))
    assert '<input type="checkbox" name="keep_value" value="1" checked>' in page
    assert "段階は付けない" in page

    r = client_in.post(
        f"/logs/{log.id}/edit/",
        {"when": "pick", "date": TODAY.isoformat(), "value": "3", "keep_value": "1", "memo": "寝不足"},
    )
    log.refresh_from_db()
    assert (r.status_code, log.value, log.memo) == (204, None, "寝不足")


def test_履歴には_段階を_5のうちいくつかで出す(client_in, user, pain):
    record(user, pain, value="4")

    assert '<b class="num">4<small>/5</small></b>' in html(client_in.get(f"/events/{pain.id}/"))


def test_段階のイベントの詳細に_推移のカードが出る(client_in, user, pain):
    for days_ago, value in ((2, "2"), (1, "5"), (0, "3")):
        record(user, pain, days_ago, value=value)

    page = html(client_in.get(f"/events/{pain.id}/"))

    assert "<h2>段階の推移</h2>" in page and '<svg class="trend"' in page
    assert "段階を付けた記録の、新しいほうから3件で見ています" in page


def test_段階の記録がまだなければ_案内だけを出す(client_in, pain):
    assert "段階を選んで記録すると、ここに推移が出ます" in html(client_in.get(f"/events/{pain.id}/"))


# --- チェックする -------------------------------------------------------------


def test_チェックのシートは_項目が先で_日付とメモは畳んである(client_in, clean):
    page = sheet(client_in, clean)

    assert '<legend class="lbl">やったもの</legend>' in page
    for item in ITEMS:
        assert f'<input type="checkbox" name="checks" value="{item}">' in page
    assert page.index('name="checks"') < page.index("<summary>日付やメモも入れる</summary>")
    assert "選ばなくても記録できます" in page and "前回と同じもの" not in page


def test_前回と同じものに_印を入れておく(client_in, user, clean):
    record(user, clean, 1, checks=["床", "風呂"])

    page = sheet(client_in, clean)

    assert page.count('name="checks"') == 4 and page.count(" checked>") == 2
    assert '<input type="checkbox" name="checks" value="床" checked>' in page
    assert "前回と同じものに、印を入れてあります" in page


def test_長押しのシートにも_チェックの欄がある(client_in, clean):
    page = sheet(client_in, clean, compact=False)

    assert 'name="checks"' in page and "<summary>" not in page and "履歴・統計を見る" in page


def test_選んだ項目を付けて記録できる(client_in, clean):
    r = post(client_in, clean, checks=["トイレ", "床"])

    assert (r.status_code, Log.objects.get().checks) == (204, ["床", "トイレ"])


def test_何も選ばなくても記録できる(client_in, clean):
    assert (post(client_in, clean).status_code, Log.objects.get().checks) == (204, [])


def test_項目にないものが届いたら_シートに誤りを出して_選んだものを残す(client_in, clean):
    page = html(post(client_in, clean, checks=["床", "ベランダ"]))

    assert "開き直してください" in page
    assert '<input type="checkbox" name="checks" value="床" checked>' in page
    assert Log.objects.count() == 0


def test_古い画面からの1タップは_チェックなしで記録される(client_in, clean):
    r = client_in.post(f"/events/{clean.id}/record/", {"log_id": str(uuid.uuid4())})

    assert (r.status_code, Log.objects.get().checks) == (200, [])


def test_記録の編集で_チェックを直せる(client_in, user, clean):
    record(user, clean, 1, checks=["風呂"])
    log = record(user, clean, checks=["床"])

    page = html(client_in.get(f"/logs/{log.id}/edit/"))
    assert '<input type="checkbox" name="checks" value="床" checked>' in page
    assert page.count(" checked>") == 1 and "前回と同じもの" not in page

    r = client_in.post(
        f"/logs/{log.id}/edit/", {"when": "pick", "date": TODAY.isoformat(), "checks": ["トイレ", "キッチン"]}
    )
    log.refresh_from_db()
    assert (r.status_code, log.checks) == (204, ["トイレ", "キッチン"])


def test_記録の編集には_その記録に残っている前の項目も出す(client_in, user, clean):
    log = record(user, clean, checks=["床"])
    ev_svc.update_event(
        user,
        clean.id,
        name="掃除",
        emoji="🧹",
        color="teal",
        streak_unit="day",
        number_kind="check",
        check_items=["窓"],
    )

    page = html(client_in.get(f"/logs/{log.id}/edit/"))

    assert '<input type="checkbox" name="checks" value="窓">' in page
    assert '<input type="checkbox" name="checks" value="床" checked>' in page


def test_履歴に_チェックした項目を出す(client_in, user, clean):
    record(user, clean, checks=["床", "風呂"])
    record(user, clean, 1)

    page = html(client_in.get(f"/events/{clean.id}/"))

    assert '<div class="chk">床・風呂</div>' in page
    assert page.count("メモなし") == 1  # チェックもメモもない記録だけ


def test_チェックのイベントの詳細に_どれを何回やったかが出る(client_in, user, clean):
    record(user, clean, 2, checks=["床", "風呂"])
    record(user, clean, 1, checks=["床"])

    page = html(client_in.get(f"/events/{clean.id}/"))

    assert "<h2>どれを何回</h2>" in page
    assert page.count('<li class="hbar') == 4
    assert '<span class="hn">床</span>' in page and '<b class="hv">2<small>回</small></b>' in page
    assert '<rect x="0" y="0" width="100" height="10"/>' in page  # いちばん多い項目が、いっぱいの長さ
    assert '<rect x="0" y="0" width="50" height="10"/>' in page
    assert "チェックを付けた記録 2件から数えています" in page


def test_チェックの記録がまだなければ_案内だけを出す(client_in, clean):
    page = html(client_in.get(f"/events/{clean.id}/"))

    assert "チェックを付けて記録すると、ここに回数が出ます" in page and '<li class="hbar' not in page


def test_チェックしないイベントの詳細には_回数のカードがない(client_in, event):
    assert "どれを何回" not in html(client_in.get(f"/events/{event.id}/"))
