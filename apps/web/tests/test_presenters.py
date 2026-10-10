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


def test_カレンダーは日曜始まりで未来の日が分かる():
    weeks = calendar_weeks(2026, 10, {date(2026, 10, 9)}, TODAY)
    first = weeks[0]
    assert first[0].date.weekday() == 6  # 日曜
    days = {c.date: c for w in weeks for c in w if c.in_month}
    assert days[date(2026, 10, 9)].has_log and not days[date(2026, 10, 9)].is_future
    assert days[date(2026, 10, 11)].is_future


def test_月の移動は年をまたぐ():
    assert shift_month(2026, 1, -1) == (2025, 12)
    assert shift_month(2026, 12, 1) == (2027, 1)
