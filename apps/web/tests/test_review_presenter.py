"""ふりかえりの草（GitHub と同じ横並び、決定 058）の組み立て。"""

from datetime import date, timedelta

from apps.core.testing import TODAY
from apps.events.models import Event
from apps.events.services.review import DayCount, YearReview
from apps.web.presenters import year_weeks

START = date(2025, 10, 5)  # 2026-10-10（土）の週から52週前の日曜


def review(days, event=None):
    return YearReview(start=START, end=TODAY, event=event, days=days, week_start="sun")


def cells_of(grid):
    return {c.date: c for week in grid.weeks for c in week}


def test_53週を古い順に並べ_1週は日曜から土曜の7日():
    grid = year_weeks(review({}), TODAY)
    assert len(grid.weeks) == 53
    assert [c.date for c in grid.weeks[0]] == [START + timedelta(i) for i in range(7)]
    assert grid.weeks[-1][-1].date == TODAY


def test_月の見出しは_その月の1日がある週に付ける():
    grid = year_weeks(review({}), TODAY)
    labels = [(i, label) for i, label in enumerate(grid.month_labels) if label]
    # 2025-10-05 の週には1日がない。11月1日（土）は 10-26 の週
    assert labels[0] == (3, "11月") and labels[-1][1] == "10月"
    assert len(labels) == 12


def test_すべてでは_濃さは_やったイベントの種類の数で_4つで頭打ち():
    days = {date(2026, 10, 1): DayCount(3, 1), date(2026, 10, 2): DayCount(2, 2), date(2026, 10, 3): DayCount(9, 6)}
    cells = cells_of(year_weeks(review(days), TODAY))
    assert [cells[date(2026, 10, d)].level for d in (1, 2, 3, 4)] == [1, 2, 4, 0]


def test_イベントで絞ると_やった日はいつも同じ濃さ():
    days = {date(2026, 10, 1): DayCount(3, 1)}
    cells = cells_of(year_weeks(review(days, Event(color="sky")), TODAY))
    assert (cells[date(2026, 10, 1)].level, cells[date(2026, 10, 2)].level) == (1, 0)


def test_今日より後の日は_先の日として印を付ける():
    from apps.web.presenters import HeatCell

    grid = year_weeks(review({}), date(2026, 10, 7))  # 水曜。木〜土は先の日
    last = grid.weeks[-1]
    assert [c.is_future for c in last] == [False, False, False, False, True, True, True]
    assert isinstance(last[0], HeatCell)


def test_月曜始まりなら_1週は月曜から日曜で_左の見出しは月水金が上から1_3_5段目():
    start = date(2025, 10, 6)  # 月曜
    grid = year_weeks(YearReview(start=start, end=TODAY, event=None, days={}, week_start="mon"), TODAY)
    assert grid.weeks[0][0].date == start and grid.weeks[0][0].date.weekday() == 0
    assert grid.day_labels == ["月", "", "水", "", "金", "", ""]


def test_日曜始まりなら_左の見出しは月水金が2_4_6段目():
    grid = year_weeks(review({}), TODAY)
    assert grid.day_labels == ["", "月", "", "水", "", "金", ""]
