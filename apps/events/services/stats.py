"""イベント詳細の統計（SPEC 3.5、決定 011・018）。すべて local_date で計算する。"""

from dataclasses import dataclass
from datetime import date

from django.db.models import Count, Max, Min
from django.db.models.functions import ExtractMonth, ExtractYear

from apps.events.models import Event, Log, StreakUnit
from apps.events.services.dates import friendly_interval, period_index
from apps.events.services.streaks import STREAK_MIN, UNIT_WORD

SEASON_RATIO = 0.7  # 最大回数の7割以上の月を「よくやる時期」とする


@dataclass(frozen=True)
class EventStats:
    total: int
    this_year: int
    pace: str | None  # 平均間隔（記録がある日が2日以上のときだけ）
    first: date | None = None  # はじめて記録した日（決定 060）
    best_streak: int = 0  # これまでで一番長く続いた連続回数（決定 059）。連続の単位が「なし」なら 0
    unit: str = StreakUnit.NONE

    @property
    def best_streak_text(self) -> str:
        """「3週連続」。2回に届かない、または単位が「なし」なら空（出さない）。"""
        if self.best_streak < STREAK_MIN:
            return ""
        return f"{self.best_streak}{UNIT_WORD[self.unit]}連続"


def event_stats(event: Event, today: date) -> EventStats:
    logs = Log.objects.filter(event=event)
    agg = logs.aggregate(first=Min("local_date"), last=Max("local_date"), days=Count("local_date", distinct=True))
    pace = None
    if agg["days"] and agg["days"] >= 2:
        pace = friendly_interval((agg["last"] - agg["first"]).days / (agg["days"] - 1))
    return EventStats(
        total=event.log_count,
        this_year=logs.filter(local_date__year=today.year).count(),
        pace=pace,
        first=agg["first"],
        best_streak=best_streak(event),
        unit=event.streak_unit,
    )


def since_text(first: date, today: date) -> str:
    """はじめての記録が、どれくらい前か。「9日前」「10か月前」「1年2か月前」（決定 060）。"""
    days = (today - first).days
    if days == 0:
        return "今日"
    months = (today.year - first.year) * 12 + today.month - first.month - (today.day < first.day)
    if months < 1:
        return f"{days}日前"
    if months < 12:
        return f"{months}か月前"
    years, rest = divmod(months, 12)
    return f"{years}年{rest}か月前" if rest else f"{years}年前"


def best_streak(event: Event) -> int:
    """これまでで一番長く続いた連続回数。途切れても減らない（記録を消したときだけ変わる）。"""
    if event.streak_unit == StreakUnit.NONE:
        return 0
    dates = Log.objects.filter(event=event).order_by("local_date").values_list("local_date", flat=True).distinct()
    best = run = 0
    prev = None
    for d in dates.iterator():
        p = period_index(d, event.streak_unit)
        if p == prev:
            continue
        run = run + 1 if prev is not None and p == prev + 1 else 1
        best = max(best, run)
        prev = p
    return best


@dataclass(frozen=True)
class Season:
    counts: list[int]  # 1〜12月
    headline: str
    years: list[int]


def _month_ranges(months: list[int]) -> str:
    out: list[str] = []
    start = prev = None
    for m in months:
        if start is None:
            start = prev = m
        elif m == prev + 1:
            prev = m
        else:
            out.append(f"{start}月" if start == prev else f"{start}〜{prev}月")
            start = prev = m
    if start is not None:
        out.append(f"{start}月" if start == prev else f"{start}〜{prev}月")
    return "・".join(out)


def season(event: Event, year: int | None) -> Season:
    """月別の記録回数。year が None なら全期間の合計。"""
    logs = Log.objects.filter(event=event)
    years = sorted({y for y in logs.annotate(y=ExtractYear("local_date")).values_list("y", flat=True)})
    if year is not None:
        logs = logs.filter(local_date__year=year)
    counts = [0] * 12
    for row in logs.annotate(m=ExtractMonth("local_date")).values("m").annotate(n=Count("id")):
        counts[row["m"] - 1] = row["n"]
    total, top = sum(counts), max(counts)
    if total < 3:
        headline = "記録が増えると、よくやる時期がわかります"
    elif all(c >= top * SEASON_RATIO for c in counts):
        headline = "1年を通して同じくらい"
    else:
        peak = [i + 1 for i, c in enumerate(counts) if c > 0 and c >= top * SEASON_RATIO]
        headline = f"よくやるのは {_month_ranges(peak)}"
    return Season(counts=counts, headline=headline, years=years)


def calendar_days(event: Event, year: int, month: int) -> set[date]:
    return set(
        Log.objects.filter(event=event, local_date__year=year, local_date__month=month)
        .values_list("local_date", flat=True)
        .distinct()
    )
