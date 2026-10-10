"""イベント詳細の統計（SPEC 3.5、決定 011・018）。すべて local_date で計算する。"""

from dataclasses import dataclass
from datetime import date

from django.db.models import Count, Max, Min
from django.db.models.functions import ExtractMonth, ExtractYear

from apps.events.models import Event, Log
from apps.events.services.dates import friendly_interval

SEASON_RATIO = 0.7  # 最大回数の7割以上の月を「よくやる時期」とする


@dataclass(frozen=True)
class EventStats:
    total: int
    this_year: int
    pace: str | None  # 平均間隔（記録がある日が2日以上のときだけ）


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
    )


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
