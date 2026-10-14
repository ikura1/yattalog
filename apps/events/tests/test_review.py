"""ふりかえり（1年の草、決定 058）。全部のイベントをまたいで、日ごとに何をやったかを数える。"""

import uuid
from datetime import date, time, timedelta

import pytest

from apps.core.testing import TODAY, new_user
from apps.events.models import Event
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.logs import When
from apps.events.services.review import DayCount, YearReview, logs_on, weekday_summary, year_review


def record(user, event, day=TODAY, memo=""):
    when = When(date=day) if day != TODAY else None
    return log_svc.record(user, event.id, uuid.uuid7(), when, memo).log


@pytest.fixture
def sheets(user):
    return ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week")


@pytest.fixture
def water(user):
    return ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf", streak_unit="none")


def test_期間は_今週を含めて53週_日曜から今日まで(user):
    """GitHub の草と同じ並び。2026-10-10 は土曜なので、今週は 10-04（日）から。"""
    review = year_review(user, TODAY)
    assert (review.start, review.end) == (date(2025, 10, 5), TODAY)


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
    record(user, water, date(2025, 10, 4))
    record(user, water, date(2025, 10, 5))

    review = year_review(user, TODAY)

    assert list(review.days) == [date(2025, 10, 5)]


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


def weekdays_of(days):
    return weekday_summary(YearReview(start=date(2025, 10, 5), end=TODAY, event=None, days=days))


def test_曜日ごとの回数を_日曜から順に数える():
    # 2026-10-04 は日曜、10-10 は土曜
    summary = weekdays_of({date(2026, 10, 4): DayCount(2, 1), date(2026, 10, 10): DayCount(1, 1)})
    assert summary.counts == [2, 0, 0, 0, 0, 0, 1]


def test_多い曜日を_よくやる曜日として見出しにする():
    days = {date(2026, 10, 3): DayCount(5, 1), date(2026, 10, 4): DayCount(4, 1), date(2026, 10, 7): DayCount(1, 1)}
    assert weekdays_of(days).headline == "よくやるのは 日・土曜"


def test_記録が少ないうちは_わかるようになると伝える():
    assert weekdays_of({date(2026, 10, 4): DayCount(2, 1)}).headline == "記録が増えると、よくやる曜日がわかります"


def test_どの曜日も同じくらいなら_そう言う():
    days = {date(2026, 10, 4) + timedelta(i): DayCount(3, 1) for i in range(7)}
    assert weekdays_of(days).headline == "どの曜日も同じくらい"
