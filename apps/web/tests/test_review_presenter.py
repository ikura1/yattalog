"""ふりかえりの草（月ごとの小さなカレンダー、決定 058）の組み立て。"""

from datetime import date

from apps.core.testing import TODAY
from apps.events.models import Event
from apps.events.services.review import DayCount, YearReview
from apps.web.presenters import year_months


def review(days, event=None):
    return YearReview(start=date(2025, 11, 1), end=TODAY, event=event, days=days)


def test_12か月を古い順に並べ_年が変わる月と最初の月には年を付ける():
    months = year_months(review({}), TODAY)
    assert [m.label for m in months] == [
        "2025年11月",
        "12月",
        "2026年1月",
        "2月",
        "3月",
        "4月",
        "5月",
        "6月",
        "7月",
        "8月",
        "9月",
        "10月",
    ]


def test_日曜始まりで_月の外のマスは空にする():
    october = year_months(review({}), TODAY)[-1]
    first_week = october.weeks[0]
    assert len(first_week) == 7
    # 2026年10月1日は木曜。日〜水は空
    assert first_week[:4] == [None] * 4 and first_week[4].date == date(2026, 10, 1)


def test_すべてでは_濃さは_やったイベントの種類の数で_4つで頭打ち():
    days = {date(2026, 10, 1): DayCount(3, 1), date(2026, 10, 2): DayCount(2, 2), date(2026, 10, 3): DayCount(9, 6)}
    cells = {c.date: c for w in year_months(review(days), TODAY)[-1].weeks for c in w if c}
    assert [cells[date(2026, 10, d)].level for d in (1, 2, 3, 4)] == [1, 2, 4, 0]


def test_イベントで絞ると_やった日はいつも同じ濃さ():
    days = {date(2026, 10, 1): DayCount(3, 1)}
    cells = {c.date: c for w in year_months(review(days, Event(color="sky")), TODAY)[-1].weeks for c in w if c}
    assert (cells[date(2026, 10, 1)].level, cells[date(2026, 10, 2)].level) == (1, 0)


def test_月ごとの回数と_今日より後の日():
    days = {date(2026, 10, 1): DayCount(3, 2), date(2026, 10, 9): DayCount(1, 1)}
    october = year_months(review(days), TODAY)[-1]
    cells = {c.date: c for w in october.weeks for c in w if c}
    assert october.total == 4
    assert (cells[TODAY].is_future, cells[date(2026, 10, 11)].is_future) == (False, True)
