"""画面用の値の組み立て（グラフの座標・カレンダー）。"""

from datetime import date

from apps.web.presenters import calendar_weeks, season_chart, shift_month

TODAY = date(2026, 10, 10)


def test_一番多い月だけが山として印が付く():
    chart = season_chart([0, 0, 2, 9, 3, 0, 0, 0, 0, 0, 0, 0], TODAY, 2026)
    assert [b.month for b in chart.bars if b.is_peak] == [4]


def test_記録が3回未満なら山の印は付けない():
    chart = season_chart([1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], TODAY, 2026)
    assert not any(b.is_peak for b in chart.bars)


def test_今年のまだ来ていない月だけが未来の月になる():
    assert [b.month for b in season_chart([0] * 12, TODAY, 2026).bars if b.is_future] == [11, 12]
    assert not any(b.is_future for b in season_chart([0] * 12, TODAY, 2025).bars)
    assert not any(b.is_future for b in season_chart([0] * 12, TODAY, None).bars)


def test_棒の高さは回数に比例し_描画範囲に収まる():
    chart = season_chart([0, 2, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0], TODAY, 2025)
    feb, mar = chart.bars[1], chart.bars[2]
    assert mar.height == 2 * feb.height
    assert all(b.y >= 0 and b.y + b.height <= 150 for b in chart.bars)


def test_目盛りは0から始まり最大値以上まである():
    chart = season_chart([0, 0, 0, 13, 0, 0, 0, 0, 0, 0, 0, 0], TODAY, 2025)
    values = [v for v, _ in chart.gridlines]
    assert values[0] == 0 and values[-1] >= 13


def test_カレンダーは週の始まりから並び_未来の日が分かる():
    assert calendar_weeks(2026, 10, set(), TODAY)[0][0].date.weekday() == 0  # 既定は月曜（決定 066）
    weeks = calendar_weeks(2026, 10, {date(2026, 10, 9)}, TODAY, "sun")
    first = weeks[0]
    assert first[0].date.weekday() == 6  # 日曜
    days = {c.date: c for w in weeks for c in w if c.in_month}
    assert days[date(2026, 10, 9)].has_log and not days[date(2026, 10, 9)].is_future
    assert days[date(2026, 10, 11)].is_future


def test_月の移動は年をまたぐ():
    assert shift_month(2026, 1, -1) == (2025, 12)
    assert shift_month(2026, 12, 1) == (2027, 1)


# --- タイルの読み上げ（アクセシビリティの約束、レビュー2回目 #9） --------------------------------

from datetime import timedelta  # noqa: E402

from apps.core.testing import NOW  # noqa: E402
from apps.events.models import Event  # noqa: E402
from apps.events.services.dates import period_index  # noqa: E402
from apps.spaces.models import Space  # noqa: E402
from apps.web.presenters import tile  # noqa: E402


def make_event(**kw) -> Event:
    defaults = dict(name="シーツ交換", emoji="🛏️", color="sky", streak_unit="day", last_local_date=None, space=Space())
    return Event(**{**defaults, **kw})


def test_読み上げにはダブルタップで記録できることが含まれる():
    assert tile(make_event(), TODAY).aria_label.endswith("ダブルタップで記録")


def test_一度も記録していないイベントの読み上げ():
    assert tile(make_event(), TODAY).aria_label.startswith("シーツ交換、まだ記録なし")


def test_今日やったイベントの読み上げ():
    assert "今日やった" in tile(make_event(last_local_date=TODAY), TODAY).aria_label


def test_さっきやったイベントの読み上げ():
    e = make_event(last_local_date=TODAY, last_occurred_at=NOW - timedelta(minutes=5))
    assert "シーツ交換、さっきやった" in tile(e, TODAY, NOW).aria_label


def test_数時間前にやったイベントの読み上げ():
    e = make_event(last_local_date=TODAY, last_occurred_at=NOW - timedelta(hours=3))
    t = tile(e, TODAY, NOW)
    assert (t.number, t.unit, t.is_today) == ("3", "時間前", True)
    assert "シーツ交換、3時間前にやった" in t.aria_label


def test_経過日数の読み上げ():
    assert "シーツ交換、5日前にやった" in tile(make_event(last_local_date=TODAY - timedelta(5)), TODAY).aria_label


def test_今日はまだの連続記録も読み上げる():
    yesterday = TODAY - timedelta(1)
    e = make_event(last_local_date=yesterday, streak_count=3, streak_period=period_index(yesterday, "day"))
    assert "3日連続（今日はまだ）" in tile(e, TODAY).aria_label


# --- 詳細画面：月や年で丸めたときは、正確な日数も出す（レビュー D9） ---


def test_月や年で丸めて出すときは_正確な日数も持つ():
    assert tile(make_event(last_local_date=TODAY - timedelta(63)), TODAY).exact_days == "63日前"
    assert tile(make_event(last_local_date=TODAY - timedelta(800)), TODAY).exact_days == "800日前"


def test_日数や時間でそのまま出しているときは_正確な日数を重ねて出さない():
    assert tile(make_event(last_local_date=TODAY - timedelta(59)), TODAY).exact_days == ""
    assert tile(make_event(last_local_date=TODAY), TODAY).exact_days == ""
    assert tile(make_event(), TODAY).exact_days == ""


def test_前回の日付は_年が違うときは年も出す():
    from datetime import date

    from apps.web.templatetags.yl import rel_day

    assert rel_day(date(2026, 8, 8), TODAY) == "8月8日"
    assert rel_day(date(2024, 8, 1), TODAY) == "2024年8月1日"
    assert rel_day(TODAY - timedelta(1), TODAY) == "昨日"
