"""段階で選ぶ・チェックする（決定 076）。記録のしかたは、イベントごとに1つ。"""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.core.testing import TODAY
from apps.events.models import Log
from apps.events.services import checks, numbers
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.logs import When

ITEMS = ["床", "トイレ", "風呂", "キッチン"]


@pytest.fixture
def pain(user):
    return ev_svc.create_event(user, name="頭痛", emoji="🤕", color="grape", number_kind="scale")


@pytest.fixture
def clean(user):
    return ev_svc.create_event(user, name="掃除", emoji="🧹", color="teal", number_kind="check", check_items=ITEMS)


@pytest.fixture
def plain(user):
    return ev_svc.create_event(user, name="散髪", emoji="✂️", color="sky")


def record(user, event, days_ago=0, **kw):
    return log_svc.record(user, event.id, uuid.uuid7(), When(date=TODAY - timedelta(days_ago)), **kw).log


def edit_event(user, event, **kw):
    return ev_svc.update_event(
        user, event.id, name=event.name, emoji=event.emoji, color=event.color, streak_unit="day", **kw
    )


# --- 記録のしかた -------------------------------------------------------------


def test_記録のしかたごとに_何を聞くかが決まる(user, plain, pain, clean):
    run = ev_svc.create_event(user, name="ランニング", emoji="🏃", color="leaf", number_kind="sum", number_unit="km")
    #                     押すと聞く / 数字を残す / 段階 / チェック
    assert (plain.asks, plain.has_number, plain.is_scale, plain.is_check) == (False, False, False, False)
    assert (run.asks, run.has_number, run.is_scale, run.is_check) == (True, True, False, False)
    assert (pain.asks, pain.has_number, pain.is_scale, pain.is_check) == (True, True, True, False)
    assert (clean.asks, clean.has_number, clean.is_scale, clean.is_check) == (True, False, False, True)


def test_段階とチェックのイベントは_単位を持たない(user):
    event = ev_svc.create_event(user, name="頭痛", emoji="🤕", color="grape", number_kind="scale", number_unit="点")
    assert event.number_unit == ""


# --- 段階で選ぶ ---------------------------------------------------------------


@pytest.mark.parametrize("raw", ["1", "3", "5", "５", 4])
def test_段階は_1から5で記録できる(user, pain, raw):
    assert record(user, pain, value=raw).value == Decimal(str(raw).replace("５", "5"))


@pytest.mark.parametrize("raw", ["0", "6", "2.5", "-1", "つらい"])
def test_段階として読めないものは断る(user, pain, raw):
    with pytest.raises(ValidationError, match="1〜5"):
        record(user, pain, value=raw)
    assert not Log.objects.filter(event=pain).exists()


def test_段階は_送られなければ空のまま記録する(user, pain):
    """古い画面からの1タップ。"""
    assert record(user, pain).value is None


def test_編集で段階を変えられる(user, pain):
    log = record(user, pain, value="2")
    assert log_svc.edit(user, log.id, When(date=TODAY), "", value="4").value == Decimal(4)


def test_編集で_段階をいまのままにできる(user, pain):
    """段階のない記録や、前の記録のしかたで付けた数字を、メモを直すだけで書き換えない。"""
    log = record(user, pain)
    edited = log_svc.edit(user, log.id, When(date=TODAY), "寝不足", value="3", keep_value=True)
    assert (edited.value, edited.memo) == (None, "寝不足")


def test_段階として使える数字かどうかを見分ける():
    assert [numbers.scale_of(v) for v in (Decimal(1), Decimal("5.000"), None, Decimal("62.5"), Decimal(0))] == [
        1,
        5,
        None,
        None,
        None,
    ]


def test_段階のイベントは_推移で見る(user, pain):
    for days_ago, value in ((2, "2"), (1, "5"), (0, "3")):
        record(user, pain, days_ago, value=value)
    found = numbers.number_stats(pain, TODAY)
    assert (found.kind, found.latest, found.lowest, found.highest, found.count) == ("scale", 3, 2, 5, 3)
    assert found.average == Decimal("3.33")


def test_段階のイベントには_よく使う数字を出さない(user, pain):
    for _ in range(3):
        record(user, pain, value="4")
    assert numbers.frequent_values(pain) == []


# --- チェックする：項目 -------------------------------------------------------


def test_チェックする項目を決めて_イベントを作れる(clean):
    assert clean.check_items == ITEMS


def test_項目は_前後の空白と空の行を落とし_同じ名前は1つにする(user):
    event = ev_svc.create_event(
        user, name="掃除", emoji="🧹", color="teal", number_kind="check", check_items=[" 床 ", "", "トイレ", "床"]
    )
    assert event.check_items == ["床", "トイレ"]


def test_チェックするイベントには_項目が1つは要る(user):
    with pytest.raises(ValidationError, match="1つ以上"):
        ev_svc.create_event(user, name="掃除", emoji="🧹", color="teal", number_kind="check", check_items=[" "])


def test_項目が多すぎると断る(user):
    with pytest.raises(ValidationError, match="8個まで"):
        ev_svc.create_event(
            user, name="掃除", emoji="🧹", color="teal", number_kind="check", check_items=[f"場所{i}" for i in range(9)]
        )


def test_項目の名前が長すぎると断る(user):
    with pytest.raises(ValidationError, match="12文字まで"):
        ev_svc.create_event(user, name="掃除", emoji="🧹", color="teal", number_kind="check", check_items=["あ" * 13])


def test_編集で項目を変えられる(user, clean):
    assert edit_event(user, clean, number_kind="check", check_items=["床", "窓"]).check_items == ["床", "窓"]


def test_編集で項目を送らなければ_そのまま(user, clean):
    """項目の欄がない古い画面からの保存で、消さない。"""
    assert edit_event(user, clean, number_kind="check").check_items == ITEMS
    assert edit_event(user, clean).check_items == ITEMS


def test_ほかの記録のしかたに変えても_項目は覚えておく(user, clean):
    """「なし」に変えて戻したときに、打ち直さなくて済む。"""
    edited = edit_event(user, clean, number_kind="none", check_items=ITEMS)
    assert (edited.is_check, edited.check_items) == (False, ITEMS)


# --- チェックする：記録 -------------------------------------------------------


def test_選んだ項目を付けて記録できる(user, clean):
    assert record(user, clean, checks=["トイレ", "床"]).checks == ["床", "トイレ"]  # 項目の順にそろえる


def test_何も選ばなくても記録できる(user, clean):
    assert record(user, clean, checks=[]).checks == []
    assert record(user, clean).checks == []


def test_項目にないものは断る(user, clean):
    """項目を変えたあとの、古いシートから。黙って捨てない。"""
    with pytest.raises(ValidationError, match="開き直して"):
        record(user, clean, checks=["床", "ベランダ"])
    assert not Log.objects.filter(event=clean).exists()


def test_チェックしないイベントでは_送られた項目を捨てる(user, plain):
    assert record(user, plain, checks=["床"]).checks == []


def test_同じIDで送り直しても_チェックは変わらない(user, clean):
    log_id = uuid.uuid7()
    log_svc.record(user, clean.id, log_id, checks=["床"])
    assert log_svc.record(user, clean.id, log_id, checks=["風呂"]).log.checks == ["床"]


def test_編集でチェックを変えられる(user, clean):
    log = record(user, clean, checks=["床"])
    assert log_svc.edit(user, log.id, When(date=TODAY), "", checks=["風呂", "キッチン"]).checks == ["風呂", "キッチン"]


def test_編集でチェックを送らなければ_そのまま(user, clean):
    log = record(user, clean, checks=["床"])
    assert log_svc.edit(user, log.id, When(date=TODAY), "メモ").checks == ["床"]


def test_項目の名前を変えても_前の記録は前の名前のまま(user, clean):
    log = record(user, clean, checks=["床", "風呂"])
    edit_event(user, clean, number_kind="check", check_items=["フローリング", "風呂"])
    log.refresh_from_db()
    assert log.checks == ["床", "風呂"]


def test_前の名前の付いた記録を編集しても_前の名前は残せる(user, clean):
    log = record(user, clean, checks=["床", "風呂"])
    edit_event(user, clean, number_kind="check", check_items=["フローリング", "風呂"])
    edited = log_svc.edit(user, log.id, When(date=TODAY), "", checks=["床", "フローリング"])
    assert edited.checks == ["フローリング", "床"]  # いまの項目が先、前の名前は後ろ


def test_チェックしないイベントに変えたあとの編集では_チェックはそのまま(user, clean):
    log = record(user, clean, checks=["床"])
    edit_event(user, clean, number_kind="none")
    assert log_svc.edit(user, log.id, When(date=TODAY), "", checks=[]).checks == ["床"]


# --- チェックする：前回と回数 -------------------------------------------------


def test_前回のチェックは_いちばん新しい記録のもの(user, clean):
    record(user, clean, 2, checks=["床", "風呂"])
    record(user, clean, 1, checks=["トイレ"])
    assert checks.last_checks(clean) == ["トイレ"]


def test_前回のチェックに_いまはない項目は入れない(user, clean):
    record(user, clean, checks=["床", "風呂"])
    edit_event(user, clean, number_kind="check", check_items=["風呂", "窓"])
    clean.refresh_from_db()
    assert checks.last_checks(clean) == ["風呂"]


def test_記録がなければ_前回のチェックは空(clean):
    assert checks.last_checks(clean) == []


def test_どれを何回やったかを_項目の順に数える(user, clean):
    record(user, clean, 2, checks=["床", "風呂"])
    record(user, clean, 1, checks=["床"])
    record(user, clean, 0, checks=[])
    found = checks.check_stats(clean)
    assert found.rows == [("床", 2), ("トイレ", 0), ("風呂", 1), ("キッチン", 0)]
    assert (found.count, found.top) == (2, 2)  # チェックの付いた記録は2件、いちばん多い項目は2回


def test_いまはない項目も_回数があれば後ろに出す(user, clean):
    record(user, clean, checks=["床", "風呂"])
    edit_event(user, clean, number_kind="check", check_items=["風呂", "窓"])
    clean.refresh_from_db()
    assert checks.check_stats(clean).rows == [("風呂", 1), ("窓", 0), ("床", 1)]


def test_チェックしないイベントには_回数の統計がない(plain):
    assert checks.check_stats(plain) is None
