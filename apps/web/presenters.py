"""画面に出す値を組み立てる（サービス層の結果 → テンプレート用の値）。"""

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from apps.events.models import Event
from apps.events.services.dates import elapsed, now_utc
from apps.events.services.review import YearReview
from apps.events.services.stats import MonthDays, Tendency
from apps.events.services.streaks import StreakState, streak_state

ROUNDED_FROM_DAYS = 60  # これ以上は「Nか月前」「N年前」に丸める（SPEC 3.3）


@dataclass(frozen=True)
class Tile:
    event: Event
    number: str
    unit: str
    is_today: bool
    never: bool
    streak: StreakState | None
    days: int | None = None  # 最新の記録からの日数（暦日）。一度も記録していなければ None

    @property
    def exact_days(self) -> str:
        """月や年に丸めて出しているときの、正確な日数（「63日前」）。丸めていなければ空（レビュー D9）。"""
        if self.days is None or self.days < ROUNDED_FROM_DAYS:
            return ""
        return f"{self.days}日前"

    @property
    def streak_unit_label(self) -> str:
        if not self.streak or self.streak.unit == "day":
            return ""
        return {"week": "週", "month": "か月"}[self.streak.unit]

    @property
    def aria_label(self) -> str:
        e = self.event
        if self.never:
            state = "まだ記録なし"
        elif self.unit:
            state = f"{self.number}{self.unit}にやった"  # 「3時間前にやった」「5日前にやった」
        else:
            state = f"{self.number}やった"  # 「さっきやった」「今日やった」
        s = f"{e.name}、{state}"
        if self.streak:
            s += f"、{self.streak.text}" + ("" if self.streak.current else self.streak.pending_text)
        return s + "。ダブルタップで記録"


def tile(event: Event, today: date, now: datetime | None = None) -> Tile:
    el = elapsed(event.last_local_date, today, event.last_occurred_at, now or now_utc())
    number, unit = el.label
    return Tile(
        event=event,
        number=number,
        unit=unit,
        is_today=el.days == 0,
        never=el.days is None,
        streak=streak_state(event.streak_count, event.streak_period, event.streak_unit, today),
        days=el.days,
    )


# --- イベント詳細：よくやる時期のグラフ（SVG の座標） --------------------------------

CHART_W, CHART_H = 320, 150
CHART_LEFT, CHART_RIGHT, CHART_TOP, CHART_BOTTOM = 22, 6, 12, 22


def _nice_step(top: int) -> int:
    for limit, step in ((4, 1), (10, 2), (20, 5), (50, 10)):
        if top <= limit:
            return step
    return 20


@dataclass(frozen=True)
class Bar:
    month: int
    count: int
    x: float
    y: float
    width: float
    height: float
    center: float
    slot_x: float
    slot_width: float
    is_peak: bool
    is_future: bool


@dataclass(frozen=True)
class SeasonChart:
    bars: list[Bar]
    gridlines: list[tuple[int, float]]  # (目盛りの値, y 座標)
    left: int = CHART_LEFT
    right: int = CHART_W - CHART_RIGHT
    label_y: int = CHART_H - 6


def season_chart(counts: list[int], today: date, year: int | None) -> SeasonChart:
    """月別の回数から棒グラフの座標を作る。year が今年なら、まだ来ていない月を薄くする。"""
    top = max(counts, default=0)
    step = _nice_step(top)
    ceiling = max(step, -(-top // step) * step)
    plot_h = CHART_H - CHART_TOP - CHART_BOTTOM
    slot = (CHART_W - CHART_LEFT - CHART_RIGHT) / 12
    bar_w = min(16, slot * 0.56)

    def y_of(v: float) -> float:
        return round(CHART_TOP + plot_h * (1 - v / ceiling), 1)

    show_peak = sum(counts) >= 3
    bars = []
    for i, c in enumerate(counts):
        center = CHART_LEFT + slot * i + slot / 2
        y = y_of(c)
        bars.append(
            Bar(
                month=i + 1,
                count=c,
                x=round(center - bar_w / 2, 1),
                y=y,
                width=round(bar_w, 1),
                height=round(CHART_H - CHART_BOTTOM - y, 1),
                center=round(center, 1),
                slot_x=round(CHART_LEFT + slot * i, 1),
                slot_width=round(slot, 1),
                is_peak=show_peak and c == top and c > 0,
                is_future=year == today.year and i + 1 > today.month,
            )
        )
    grid_step = step if ceiling // step <= 4 else step * 2
    return SeasonChart(bars=bars, gridlines=[(v, y_of(v)) for v in range(0, ceiling + 1, grid_step)])


# --- イベント詳細：カレンダー ------------------------------------------------------


@dataclass(frozen=True)
class CalendarDay:
    date: date
    in_month: bool
    has_log: bool
    is_future: bool


def calendar_weeks(year: int, month: int, marked: set[date], today: date) -> list[list[CalendarDay]]:
    """日曜始まりの月のカレンダー。"""
    weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(year, month)
    return [[CalendarDay(d, d.month == month, d in marked, d > today) for d in week] for week in weeks]


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    m = year * 12 + (month - 1) + delta
    return (m // 12, m % 12 + 1)


# --- ふりかえり：1年の草（GitHub と同じ横並び、決定 058） ------------------------------

MAX_LEVEL = 4  # 濃さの段階（0 は記録なし）


@dataclass(frozen=True)
class HeatCell:
    date: date
    level: int  # 0〜4
    logs: int
    is_future: bool


@dataclass(frozen=True)
class HeatGrid:
    weeks: list[list[HeatCell]]  # 古い週から。1週は日曜から土曜
    month_labels: list[str]  # 週ごとの、上に出す月（その月の1日がある週だけ「11月」。ほかは空）

    @property
    def columns(self) -> list[tuple[str, list[HeatCell]]]:
        """テンプレート用：（月の見出し、その週の7日）の組。"""
        return list(zip(self.month_labels, self.weeks, strict=True))


def year_weeks(review: YearReview, today: date) -> HeatGrid:
    """53週分を古い順に。濃さは、すべてならやったイベントの種類の数、1つに絞っていれば記録があるかどうか。"""
    weeks, labels = [], []
    start = review.start
    while start <= today:
        week = [_heat_cell(start + timedelta(i), review, today) for i in range(7)]
        first = next((c.date for c in week if c.date.day == 1), None)
        weeks.append(week)
        labels.append(f"{first.month}月" if first else "")
        start += timedelta(weeks=1)
    return HeatGrid(weeks=weeks, month_labels=labels)


def _heat_cell(d: date, review: YearReview, today: date) -> HeatCell:
    count = review.days.get(d)
    if count is None:
        level = 0
    elif review.event:
        level = 1
    else:
        level = min(count.kinds, MAX_LEVEL)
    return HeatCell(date=d, level=level, logs=count.logs if count else 0, is_future=d > today)


@dataclass(frozen=True)
class TendencyBar:
    """よくやる曜日・時間帯の棒。"""

    name: str  # 「土」「朝」
    count: int
    height: int  # 一番多いものを 100 とした高さ
    is_peak: bool

    @property
    def y(self) -> int:
        """SVG（高さ 100）での、棒の上端。CSP で style 属性が使えないので、高さは SVG の属性で渡す。"""
        return 100 - self.height


def tendency_bars(t: Tendency) -> list[TendencyBar]:
    top = max(t.counts) or 1
    return [
        TendencyBar(name=n, count=c, height=round(c * 100 / top), is_peak=p)
        for n, c, p in zip(t.names, t.counts, t.peaks, strict=True)
    ]


@dataclass(frozen=True)
class MonthDayCell:
    day: int  # 1〜31
    count: int
    level: int  # 0〜4


def month_day_cells(md: MonthDays) -> list[MonthDayCell]:
    """よくやる日にちのマス（1日〜31日、決定 060）。"""
    return [
        MonthDayCell(day=i + 1, count=c, level=lv) for i, (c, lv) in enumerate(zip(md.counts, md.levels, strict=True))
    ]
