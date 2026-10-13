from datetime import UTC, date, datetime, timedelta

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from apps.core.testing import NOW
from apps.events.services.dates import Elapsed, elapsed, friendly_interval, period_index, today_in
from apps.events.services.streaks import compute_streak, streak_state


def desc(*ds):
    return sorted(ds, reverse=True)


D = date(2026, 10, 10)  # 土曜


def test_week_starts_on_monday():
    mon, sun, next_mon = date(2026, 10, 5), date(2026, 10, 11), date(2026, 10, 12)
    assert period_index(mon, "week") == period_index(sun, "week")
    assert period_index(next_mon, "week") == period_index(sun, "week") + 1


def test_month_period_crosses_year():
    assert period_index(date(2027, 1, 1), "month") == period_index(date(2026, 12, 31), "month") + 1


def test_daily_streak_counts_consecutive_days():
    ds = desc(D, D - timedelta(1), D - timedelta(2), D - timedelta(4))
    assert compute_streak(ds, "day") == (3, D.toordinal())


def test_same_day_counts_once():
    assert compute_streak(desc(D, D, D - timedelta(1)), "day")[0] == 2


def test_weekly_streak():
    ds = desc(D, D - timedelta(7), D - timedelta(14), D - timedelta(30))
    assert compute_streak(ds, "week")[0] == 3


def test_none_unit():
    assert compute_streak(desc(D), "none") == (0, None)


def test_state_current_pending_broken():
    count, last = compute_streak(desc(D - timedelta(1), D - timedelta(2)), "day")
    assert streak_state(count, last, "day", D - timedelta(1)).current is True
    pending = streak_state(count, last, "day", D)
    assert pending is not None and pending.current is False and pending.pending_text == "（今日はまだ）"
    assert streak_state(count, last, "day", D + timedelta(1)) is None


def test_single_period_has_no_badge():
    count, last = compute_streak(desc(D), "day")
    assert streak_state(count, last, "day", D) is None


def naive_streak(days: set[date], unit: str) -> int:
    ps = {period_index(d, unit) for d in days}
    if not ps:
        return 0
    p, n = max(ps), 0
    while p in ps:
        n += 1
        p -= 1
    return n


@given(
    st.sets(st.integers(min_value=0, max_value=400), max_size=80),
    st.sampled_from(["day", "week", "month"]),
)
def test_streak_matches_naive(offsets, unit):
    days = {D - timedelta(o) for o in offsets}
    assert compute_streak(sorted(days, reverse=True), unit)[0] == naive_streak(days, unit)


def test_elapsed_labels():
    assert elapsed(None, D).label == ("—", "")
    assert elapsed(D, D).label == ("今日", "")
    assert elapsed(D - timedelta(59), D).label == ("59", "日前")
    assert elapsed(D - timedelta(60), D).label == ("2", "か月前")
    assert elapsed(D - timedelta(730), D).label == ("2", "年前")


def test_elapsed_never_negative_after_crossing_timezones():
    # 日本で 10/10 に記録 → ロサンゼルスに移動すると現地はまだ 10/9
    assert elapsed(D, D - timedelta(1)) == Elapsed(0)


def test_月単位の連続は年をまたいでも続く():
    ds = desc(date(2027, 1, 5), date(2026, 12, 20), date(2026, 11, 1))
    assert compute_streak(ds, "month")[0] == 3


def test_週単位は日曜と翌日の月曜で別の週になる():
    sun, mon = date(2026, 10, 11), date(2026, 10, 12)
    assert compute_streak(desc(mon, sun), "week") == (2, period_index(mon, "week"))


def test_月単位の今月はまだの判定():
    count, last = compute_streak(desc(date(2026, 9, 3), date(2026, 8, 30)), "month")
    state = streak_state(count, last, "month", date(2026, 10, 10))
    assert state is not None and (state.current, state.text, state.pending_text) == (
        False,
        "2か月連続",
        "（今月はまだ）",
    )


def test_friendly_interval():
    assert friendly_interval(1) == "ほぼ毎日"
    assert friendly_interval(7) == "だいたい7日ごと"
    assert friendly_interval(14) == "だいたい2週間ごと"
    assert friendly_interval(60) == "だいたい2か月ごと"


def test_タイムゾーン名の検証():
    from apps.events.services.dates import is_valid_timezone

    assert is_valid_timezone("Asia/Tokyo") and is_valid_timezone("America/Los_Angeles")
    assert not any(map(is_valid_timezone, ["", "Not/AZone", "../etc/passwd", "x" * 100]))


# --- 今日の記録は時間で出す（決定 034） ---------------------------------------------


def test_今日の時刻ありの記録は_1時間未満なら_さっき_それ以上は_N時間():
    assert elapsed(D, D, NOW - timedelta(seconds=30), NOW).label == ("さっき", "")
    assert elapsed(D, D, NOW - timedelta(minutes=59), NOW).label == ("さっき", "")
    assert elapsed(D, D, NOW - timedelta(minutes=60), NOW).label == ("1", "時間前")
    assert elapsed(D, D, NOW - timedelta(hours=5, minutes=50), NOW).label == ("5", "時間前")


def test_今日の時刻なしの記録は_今日_のまま():
    assert elapsed(D, D, None, NOW).label == ("今日", "")


def test_日付が変わったら_2時間前の記録でも_1日():
    assert elapsed(D - timedelta(1), D, NOW - timedelta(hours=2), NOW).label == ("1", "日前")


def test_時計のずれで記録が少し先の時刻でも_さっき():
    assert elapsed(D, D, NOW + timedelta(seconds=40), NOW).label == ("さっき", "")


# --- 日付の境目（レビュー E10）。不具合が出やすいところを、値を決めて確かめる ---------------


def test_うるう日をはさんでも_毎日の連続は途切れない():
    days = [date(2028, 3, 1), date(2028, 2, 29), date(2028, 2, 28)]
    assert compute_streak(days, "day")[0] == 3


def test_うるう年でない年は_2月28日の次が3月1日():
    assert compute_streak([date(2027, 3, 1), date(2027, 2, 28)], "day")[0] == 2
    assert period_index(date(2027, 3, 1), "day") - period_index(date(2027, 2, 28), "day") == 1


def test_月末と月初は_別の月として数える():
    jan31, feb1 = date(2026, 1, 31), date(2026, 2, 1)
    assert period_index(feb1, "month") == period_index(jan31, "month") + 1
    assert compute_streak([feb1, jan31], "month")[0] == 2


def test_年末と年始は_同じ週のことがある():
    """2026-12-31（木）と 2027-01-01（金）は、月曜始まりの同じ週。週単位では1回と数える。"""
    assert period_index(date(2026, 12, 31), "week") == period_index(date(2027, 1, 1), "week")
    assert compute_streak([date(2027, 1, 1), date(2026, 12, 31)], "week")[0] == 1


@pytest.mark.parametrize(
    "utc,tz,expected",
    [
        (datetime(2026, 10, 10, 14, 59, tzinfo=UTC), "Asia/Tokyo", date(2026, 10, 10)),  # 23:59
        (datetime(2026, 10, 10, 15, 0, tzinfo=UTC), "Asia/Tokyo", date(2026, 10, 11)),  # 0:00 ちょうど
        (datetime(2026, 12, 31, 15, 0, tzinfo=UTC), "Asia/Tokyo", date(2027, 1, 1)),  # 年をまたぐ
        (datetime(2026, 10, 10, 6, 59, tzinfo=UTC), "America/Los_Angeles", date(2026, 10, 9)),  # 夏時間（UTC-7）
        (datetime(2026, 11, 1, 8, 30, tzinfo=UTC), "America/Los_Angeles", date(2026, 11, 1)),  # 夏時間が終わる夜
        (datetime(2026, 3, 8, 9, 59, tzinfo=UTC), "America/Los_Angeles", date(2026, 3, 8)),  # 夏時間が始まる夜
        (datetime(2026, 10, 10, 3, 0, tzinfo=UTC), "Pacific/Kiritimati", date(2026, 10, 10)),  # UTC+14
        (datetime(2026, 10, 10, 3, 0, tzinfo=UTC), "Pacific/Pago_Pago", date(2026, 10, 9)),  # UTC-11
    ],
)
def test_今日の日付は_その人のタイムゾーンの0時で切り替わる(utc, tz, expected):
    assert today_in(tz, utc) == expected


def test_保存されたタイムゾーンが壊れていても_日本時間として動く():
    assert today_in("No/Such_Zone", datetime(2026, 10, 10, 15, 0, tzinfo=UTC)) == date(2026, 10, 11)


@given(st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31)), st.integers(min_value=0, max_value=4000))
@example(date(2026, 10, 10), 0)
@example(date(2026, 10, 10), 1)
@example(date(2026, 10, 10), 59)
@example(date(2026, 10, 10), 60)
@example(date(2026, 10, 10), 729)
@example(date(2026, 10, 10), 730)
def test_経過の表示は_どの日付でも_日数と食い違わない(today, ago):
    """「N日前」「Nか月前」「N年前」の数字は、実際の日数から決まる。境目（59・60、729・730）は必ず確かめる。"""
    label = elapsed(today - timedelta(ago), today).label
    if ago == 0:
        assert label == ("今日", "")
    elif ago < 60:
        assert label == (str(ago), "日前")
    elif ago < 730:
        assert label == (str(ago // 30), "か月前")
    else:
        assert label == (str(ago // 365), "年前")


@given(
    st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2035, 1, 1), timezones=st.just(UTC)),
    st.sampled_from(["Asia/Tokyo", "America/Los_Angeles", "Europe/London", "Pacific/Kiritimati", "Pacific/Pago_Pago"]),
)
def test_今日の日付は_UTC_の日付から1日より大きくはずれない(now, tz):
    assert abs((today_in(tz, now) - now.date()).days) <= 1
