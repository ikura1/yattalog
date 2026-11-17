"""数字の記録（決定 074）。イベントごとに数字を1つ、単位つきで残し、合計か推移で見る。"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.core.testing import TODAY
from apps.events.models import Log
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services import numbers
from apps.events.services.logs import When


@pytest.fixture
def run(user):
    return ev_svc.create_event(user, name="ランニング", emoji="🏃", color="leaf", number_kind="sum", number_unit="km")


@pytest.fixture
def weight(user):
    return ev_svc.create_event(user, name="体重", emoji="⚖️", color="sky", number_kind="trend", number_unit="kg")


@pytest.fixture
def plain(user):
    return ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky")


def record(user, event, value, days_ago=0):
    return log_svc.record(user, event.id, uuid.uuid7(), When(date=TODAY - timedelta(days_ago)), value=value).log


# --- イベントの設定 -----------------------------------------------------------


def test_イベントは_はじめは数字を記録しない(plain):
    assert (plain.number_kind, plain.number_unit, plain.has_number) == ("none", "", False)


def test_数字の見せ方と単位を決めてイベントを作れる(run):
    assert (run.number_kind, run.number_unit, run.has_number) == ("sum", "km", True)


def test_単位は付けなくてもよい(user):
    event = ev_svc.create_event(user, name="腕立て", emoji="💪", color="sun", number_kind="sum")
    assert (event.has_number, event.number_unit) == (True, "")


def test_知らない見せ方は断る(user):
    with pytest.raises(ValidationError):
        ev_svc.create_event(user, name="体重", emoji="⚖️", color="sky", number_kind="graph")


def test_単位が長すぎると断る(user):
    with pytest.raises(ValidationError) as e:
        ev_svc.create_event(
            user, name="体重", emoji="⚖️", color="sky", number_kind="trend", number_unit="キログラムくらいです"
        )
    assert "単位は8文字まで" in e.value.messages[0]


def test_数字を記録しないなら_単位は持たない(user):
    event = ev_svc.create_event(user, name="散髪", emoji="✂️", color="sky", number_kind="none", number_unit="km")
    assert event.number_unit == ""


def test_編集で_数字の見せ方と単位を変えられる(user, plain):
    edited = ev_svc.update_event(
        user,
        plain.id,
        name="読書",
        emoji="📚",
        color="sky",
        streak_unit="day",
        number_kind="sum",
        number_unit=" ページ ",
    )
    assert (edited.number_kind, edited.number_unit) == ("sum", "ページ")


def test_編集で数字の設定を送らなければ_そのまま(user, run):
    """開いたままの古い画面からの保存で、数字の設定が消えないように。"""
    edited = ev_svc.update_event(user, run.id, name="ラン", emoji="🏃", color="leaf", streak_unit="day")
    assert (edited.number_kind, edited.number_unit) == ("sum", "km")


def test_データベースも_知らない見せ方を受け付けない(run):
    with pytest.raises(IntegrityError), transaction.atomic():
        type(run).objects.filter(id=run.id).update(number_kind="graph")


# --- 記録 ---------------------------------------------------------------------


def test_数字を付けて記録できる(user, run):
    assert record(user, run, "5.2").value == Decimal("5.2")


@pytest.mark.parametrize(
    ("raw", "saved"),
    [("5", "5"), (" 62.5 ", "62.5"), ("６２．５", "62.5"), ("1,200", "1200"), ("0", "0"), ("5.", "5"), (7, "7")],
)
def test_全角や桁区切りの入った数字も受け取る(user, run, raw, saved):
    assert record(user, run, raw).value == Decimal(saved)


@pytest.mark.parametrize("raw", ["", "  ", None])
def test_数字は空のままでも記録できる(user, run, raw):
    assert record(user, run, raw).value is None


@pytest.mark.parametrize("raw", ["abc", "-1", "1.2345", "1e3", "NaN", "1234567890", "1.2.3", "."])
def test_数字として読めないものは断る(user, run, raw):
    with pytest.raises(ValidationError) as e:
        record(user, run, raw)
    assert "数字は" in e.value.messages[0]
    assert Log.objects.count() == 0


def test_数字を記録しないイベントでは_送られた数字を捨てる(user, plain):
    assert record(user, plain, "5.2").value is None


def test_同じIDで送り直しても_数字は変わらない(user, run):
    lid = uuid.uuid7()
    log_svc.record(user, run.id, lid, value="5")
    again = log_svc.record(user, run.id, lid, value="9")
    assert (again.created, again.log.value) == (False, Decimal("5"))


def test_編集で数字を変えられ_空にすれば外れる(user, run):
    log = record(user, run, "5")
    assert log_svc.edit(user, log.id, When(date=TODAY), "", value="7.5").value == Decimal("7.5")
    assert log_svc.edit(user, log.id, When(date=TODAY), "", value="").value is None


def test_数字を記録しないイベントに変えたあとの編集では_数字はそのまま(user, run):
    log = record(user, run, "5")
    ev_svc.update_event(user, run.id, name="ラン", emoji="🏃", color="leaf", streak_unit="day", number_kind="none")
    assert log_svc.edit(user, log.id, When(date=TODAY), "メモ", value="").value == Decimal("5")


def test_データベースも_負の数字を受け付けない(user, run):
    log = record(user, run, "5")
    with pytest.raises(IntegrityError), transaction.atomic():
        Log.objects.filter(id=log.id).update(value=Decimal("-1"))


def test_前回の数字は_数字の付いたいちばん新しい記録のもの(user, weight):
    assert numbers.last_value(weight) is None
    record(user, weight, "63", days_ago=3)
    record(user, weight, "62.5", days_ago=1)
    record(user, weight, "", days_ago=0)
    assert numbers.last_value(weight) == Decimal("62.5")


# --- よく使う数字（決定 075） ---------------------------------------------------


def test_よく使う数字は_回数の多い順に出す(user, run):
    for i, value in enumerate(["3", "5", "5", "10", "5", "3", "10", "10", "10"]):
        record(user, run, value, days_ago=i)

    assert numbers.frequent_values(run) == [Decimal("10"), Decimal("5"), Decimal("3")]


def test_同じ回数なら_新しく使ったほうが先(user, run):
    for i, value in enumerate(["3", "5", "5", "3"]):
        record(user, run, value, days_ago=i)

    assert numbers.frequent_values(run) == [Decimal("3"), Decimal("5")]


def test_1回しか入れていない数字は_よく使う数字に出さない(user, run):
    record(user, run, "5", days_ago=2)
    record(user, run, "7.5", days_ago=1)
    record(user, run, "", days_ago=0)

    assert numbers.frequent_values(run) == []


def test_書き方が違っても_同じ数字として数える(user, run):
    record(user, run, "5", days_ago=1)
    record(user, run, "5.0", days_ago=0)

    assert numbers.frequent_values(run) == [Decimal("5")]


def test_よく使う数字は_決まった数まで(user, run):
    for i in range(numbers.QUICK_MAX + 2):
        record(user, run, str(i + 1), days_ago=i * 2)
        record(user, run, str(i + 1), days_ago=i * 2 + 1)

    assert len(numbers.frequent_values(run)) == numbers.QUICK_MAX


def test_よく使う数字は_新しいほうから決まった件数だけを見る(user, run):
    record(user, run, "42", days_ago=numbers.QUICK_RECENT + 1)
    record(user, run, "42", days_ago=numbers.QUICK_RECENT)
    for i in range(numbers.QUICK_RECENT):
        record(user, run, str(100 + i), days_ago=i)

    assert numbers.frequent_values(run) == []


# --- 表示 ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "text"),
    [("5", "5"), ("62.500", "62.5"), ("1200", "1,200"), ("1234567.25", "1,234,567.25"), ("0", "0"), ("0.050", "0.05")],
)
def test_数字は_余分な0を落とし_3桁ごとに区切って出す(value, text):
    assert numbers.format_value(Decimal(value)) == text


def test_入力欄に入れる数字には_区切りを入れない():
    assert numbers.plain_value(Decimal("1200.50")) == "1200.5"
    assert numbers.plain_value(None) == ""


# --- 統計：合計 -----------------------------------------------------------------


def test_数字を記録しないイベントには_数字の統計がない(plain):
    assert numbers.number_stats(plain, TODAY) is None


def test_合計は_今月と今年とこれまでを出す(user, run):
    record(user, run, "5", days_ago=0)  # 2026-10-10
    record(user, run, "3.5", days_ago=9)  # 10-01
    record(user, run, "10", days_ago=10)  # 09-30
    record(user, run, "", days_ago=11)  # 数字なしは数えない
    log_svc.record(user, run.id, uuid.uuid7(), When(date=date(2025, 12, 31)), value="100")

    s = numbers.number_stats(run, TODAY)

    assert (s.kind, s.unit) == ("sum", "km")
    assert (s.month, s.year, s.total) == (Decimal("8.5"), Decimal("18.5"), Decimal("118.5"))
    assert s.count == 4


def test_合計は_今月までの12か月を月ごとに出す(user, run):
    record(user, run, "5", days_ago=0)
    record(user, run, "10", days_ago=10)
    log_svc.record(user, run.id, uuid.uuid7(), When(date=date(2025, 11, 1)), value="2")
    log_svc.record(user, run.id, uuid.uuid7(), When(date=date(2025, 10, 31)), value="99")  # 13か月前は入らない

    months = numbers.number_stats(run, TODAY).months

    assert [(y, m) for y, m, _ in months][0] == (2025, 11)
    assert [(y, m) for y, m, _ in months][-1] == (2026, 10)
    assert len(months) == 12
    assert [v for _, _, v in months] == [Decimal(2)] + [Decimal(0)] * 9 + [Decimal(10), Decimal(5)]


def test_数字の記録がまだなければ_合計は0で_件数も0(run):
    s = numbers.number_stats(run, TODAY)
    assert (s.month, s.year, s.total, s.count) == (Decimal(0), Decimal(0), Decimal(0), 0)


# --- 統計：推移 -----------------------------------------------------------------


def test_推移は_最新と前回との差_平均_最小_最大を出す(user, weight):
    record(user, weight, "64", days_ago=4)
    record(user, weight, "63", days_ago=2)
    record(user, weight, "", days_ago=1)
    record(user, weight, "62.4", days_ago=0)

    t = numbers.number_stats(weight, TODAY)

    assert (t.kind, t.unit, t.count) == ("trend", "kg", 3)
    assert (t.latest, t.diff) == (Decimal("62.4"), Decimal("-0.6"))
    assert (t.lowest, t.highest) == (Decimal("62.4"), Decimal("64"))
    assert t.average == Decimal("63.13")  # 小数2桁に丸める
    assert t.points == [
        (TODAY - timedelta(4), Decimal("64")),
        (TODAY - timedelta(2), Decimal("63")),
        (TODAY, Decimal("62.4")),
    ]


def test_推移は_新しいほうから決まった件数だけを見る(user, weight):
    for i in range(numbers.TREND_POINTS + 5):
        record(user, weight, str(100 + i), days_ago=i)  # 古いほど大きい

    t = numbers.number_stats(weight, TODAY)

    assert len(t.points) == numbers.TREND_POINTS
    assert t.highest == Decimal(100 + numbers.TREND_POINTS - 1)  # それより古いものは入らない
    assert t.points[-1] == (TODAY, Decimal(100))


def test_数字が1つだけなら_前回との差はない(user, weight):
    record(user, weight, "62")
    t = numbers.number_stats(weight, TODAY)
    assert (t.latest, t.diff, t.count) == (Decimal("62"), None, 1)


def test_数字の記録がまだなければ_推移は空(weight):
    t = numbers.number_stats(weight, TODAY)
    assert (t.latest, t.diff, t.average, t.count, t.points) == (None, None, None, 0, [])


@pytest.mark.parametrize(("diff", "text"), [("-0.6", "−0.6"), ("1.25", "+1.25"), ("0", "±0")])
def test_前回との差は_符号を付けて出す(diff, text):
    assert numbers.signed(Decimal(diff)) == text
