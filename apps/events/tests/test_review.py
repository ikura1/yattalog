"""ふりかえり（1年の草、決定 058）。全部のイベントをまたいで、日ごとに何をやったかを数える。"""

import uuid
from datetime import date, time, timedelta

import pytest

from apps.core.testing import TODAY, new_user
from apps.events.models import Event
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.logs import When
from apps.events.services.review import a_year_ago, logs_on, top_events, year_review


def record(user, event, day=TODAY, memo=""):
    when = When(date=day) if day != TODAY else None
    return log_svc.record(user, event.id, uuid.uuid7(), when, memo).log


@pytest.fixture
def sheets(user):
    return ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week")


@pytest.fixture
def water(user):
    return ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf", streak_unit="none")


def test_期間は_今週を含めて53週_週の始まりから今日まで(user):
    """GitHub の草と同じ並び。2026-10-10 は土曜で、既定は月曜始まりなので、今週は 10-05（月）から（決定 066）。"""
    review = year_review(user, TODAY)
    assert (review.start, review.end) == (date(2025, 10, 6), TODAY)


def test_日ごとに_記録の回数と_やったイベントの種類の数を数える(user, sheets, water):
    record(user, water)
    record(user, water)
    record(user, sheets)
    day = record(user, water, TODAY - timedelta(3)).local_date

    review = year_review(user, TODAY)

    assert (review.days[TODAY].logs, review.days[TODAY].kinds) == (3, 2)
    assert (review.days[day].logs, review.days[day].kinds) == (1, 1)
    assert (review.total, review.active_days) == (4, 2)


def test_期間より前の記録は_数えない(user, water):
    record(user, water, date(2025, 10, 5))
    record(user, water, date(2025, 10, 6))

    review = year_review(user, TODAY)

    assert list(review.days) == [date(2025, 10, 6)]


def test_イベントで絞ると_そのイベントの記録だけを数える(user, sheets, water):
    record(user, water)
    record(user, sheets)

    review = year_review(user, TODAY, sheets.id)

    assert review.event == sheets
    assert (review.days[TODAY].logs, review.total) == (1, 1)


def test_アーカイブしたイベントの記録も_すべてに数える(user, sheets):
    record(user, sheets)
    ev_svc.set_archived(user, sheets.id, True)

    assert year_review(user, TODAY).total == 1


def test_ほかの人の記録は_数えない(user, water):
    other = new_user(email="b@example.com")
    theirs = ev_svc.create_event(other, name="ひみつ", emoji="🤫", color="pink")
    record(other, theirs)

    assert year_review(user, TODAY).total == 0


def test_ほかの人のイベントでは_絞れない(user):
    other = new_user(email="b@example.com")
    theirs = ev_svc.create_event(other, name="ひみつ", emoji="🤫", color="pink")

    with pytest.raises(Event.DoesNotExist):
        year_review(user, TODAY, theirs.id)


def test_その日の記録を_時刻の順に返す_時刻なしは後(user, sheets, water):
    dateonly = record(user, sheets, TODAY - timedelta(1))
    log_svc.record(user, water.id, uuid.uuid7(), When(date=TODAY - timedelta(1), time=time(8, 30)))
    log_svc.record(user, sheets.id, uuid.uuid7(), When(date=TODAY - timedelta(1), time=time(21, 0)))

    logs = logs_on(user, TODAY - timedelta(1))

    assert [(log.event.name, log.occurred_at is None) for log in logs] == [
        ("水やり", False),
        ("シーツ交換", False),
        ("シーツ交換", True),
    ]
    assert logs[-1] == dateonly


def test_その日の記録も_イベントで絞れて_ほかの人の分は入らない(user, sheets, water):
    record(user, sheets)
    record(user, water)
    other = new_user(email="b@example.com")
    record(other, ev_svc.create_event(other, name="ひみつ", emoji="🤫", color="pink"))

    assert [log.event for log in logs_on(user, TODAY)] == [sheets, water]
    assert [log.event for log in logs_on(user, TODAY, sheets.id)] == [sheets]


# --- 1年前の今ごろ（決定 061） ---


def test_1年前の今ごろは_1年前の前後3日にやったことを_イベントごとにまとめる(user, sheets, water):
    # TODAY は 2026-10-10。1年前は 2025-10-10、前後3日は 10-07〜10-13
    for d in (date(2025, 10, 7), date(2025, 10, 13)):
        record(user, water, d)
    record(user, sheets, date(2025, 10, 10))
    record(user, sheets, date(2025, 10, 6))  # 範囲の外
    record(user, sheets, date(2025, 10, 14))  # 範囲の外

    ago = a_year_ago(user, TODAY)

    assert [(a.event.name, a.dates) for a in ago] == [
        ("水やり", [date(2025, 10, 7), date(2025, 10, 13)]),
        ("シーツ交換", [date(2025, 10, 10)]),
    ]


def test_1年前の今ごろも_イベントで絞れて_ほかの人の記録は入らない(user, sheets, water):
    record(user, sheets, date(2025, 10, 10))
    record(user, water, date(2025, 10, 10))
    other = new_user(email="b@example.com")
    record(other, ev_svc.create_event(other, name="ひみつ", emoji="🤫", color="pink"), date(2025, 10, 10))

    assert [a.event for a in a_year_ago(user, TODAY)] == [sheets, water]
    assert [a.event for a in a_year_ago(user, TODAY, water.id)] == [water]


def test_2月29日の1年前は_2月28日として数える(user, water):
    record(user, water, date(2023, 3, 2))
    assert [a.dates for a in a_year_ago(user, date(2024, 2, 29))] == [[date(2023, 3, 2)]]


# --- この1年でよくやったこと（決定 062） ---


def test_この1年でよくやったことは_回数の多いイベントから3つ(user, sheets, water):
    gym = ev_svc.create_event(user, name="筋トレ", emoji="💪", color="tomato")
    dentist = ev_svc.create_event(user, name="歯医者", emoji="🦷", color="pink")
    for d in range(3):
        record(user, water, TODAY - timedelta(d))
    for d in range(2):
        record(user, gym, TODAY - timedelta(d))
    record(user, sheets, TODAY - timedelta(5))
    record(user, dentist, date(2025, 10, 4))  # 1年（53週）より前

    top = top_events(user, TODAY)

    assert [(t.event.name, t.count) for t in top] == [("水やり", 3), ("筋トレ", 2), ("シーツ交換", 1)]


def test_この1年でよくやったことに_ほかの人の記録は入らない(user, water):
    other = new_user(email="b@example.com")
    record(other, ev_svc.create_event(other, name="ひみつ", emoji="🤫", color="pink"))
    assert top_events(user, TODAY) == []


def test_その日の記録は_多すぎるときは上限までにして_残りの数を返す(user, water, monkeypatch):
    from apps.events.services import review

    monkeypatch.setattr(review, "DAY_LIMIT", 3)
    for _ in range(5):
        record(user, water)
    logs = logs_on(user, TODAY)
    assert (len(logs), logs.more) == (3, 2)
