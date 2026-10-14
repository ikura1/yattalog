"""ふりかえり（1年の草、決定 058）。全部のイベントをまたいで、日ごとに何をやったかを数える。

濃さには、その日にやったイベントの「種類の数」を使う。ほとんどのイベントは1日に1回なので、
回数では差が出ない。やらなかった日やストリークの途切れは、数えも見せもしない。
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from django.db.models import Count, F

from apps.events.models import Event, Log
from apps.events.services.access import event_for
from apps.events.services.dates import zone
from apps.events.services.stats import SEASON_RATIO

WEEKS = 53  # 今週を含めて53週（GitHub の草と同じ）
WEEKDAY_NAMES = "日月火水木金土"  # 日曜始まり（カレンダーと同じ）
TIME_SLOTS = ("朝", "昼", "夕方", "夜")  # 4:00〜 / 11:00〜 / 16:00〜 / 19:00〜3:59


@dataclass(frozen=True)
class DayCount:
    logs: int  # 記録の回数
    kinds: int  # やったイベントの種類の数


@dataclass(frozen=True)
class YearReview:
    start: date
    end: date
    event: Event | None  # 絞っているイベント。すべてなら None
    days: dict[date, DayCount] = field(default_factory=dict)  # 記録がある日だけ

    @property
    def total(self) -> int:
        return sum(d.logs for d in self.days.values())

    @property
    def active_days(self) -> int:
        return len(self.days)


@dataclass(frozen=True)
class Tendency:
    """よくやる曜日・時間帯。決め方は「よくやる時期」と同じ（最多の7割以上を挙げる）。"""

    names: list[str]  # 「日」…「土」、「朝」…「夜」
    counts: list[int]
    headline: str
    peaks: list[bool]  # 見出しに挙げたもの


def _tendency(names, counts, *, few: str, even: str, suffix: str = "") -> Tendency:
    total, top = sum(counts), max(counts)
    peaks = [False] * len(counts)
    if total < 3:
        headline = few
    elif all(c >= top * SEASON_RATIO for c in counts):
        headline = even
    else:
        peaks = [c >= top * SEASON_RATIO for c in counts]
        headline = f"よくやるのは {'・'.join(n for n, p in zip(names, peaks, strict=True) if p)}{suffix}"
    return Tendency(names=list(names), counts=counts, headline=headline, peaks=peaks)


def weekday_summary(review: YearReview) -> Tendency:
    """よくやる曜日。1年分の記録を曜日ごと（日曜から）に数える。"""
    counts = [0] * 7
    for day, count in review.days.items():
        counts[(day.weekday() + 1) % 7] += count.logs
    return _tendency(
        WEEKDAY_NAMES, counts, few="記録が増えると、よくやる曜日がわかります", even="どの曜日も同じくらい", suffix="曜"
    )


def _slot(hour: int) -> int:
    if 4 <= hour < 11:
        return 0
    if 11 <= hour < 16:
        return 1
    if 16 <= hour < 19:
        return 2
    return 3


def time_of_day(user, today: date, event_id=None) -> Tendency:
    """よくやる時間帯（決定 060）。1年分の、時刻つきの記録だけを、記録したときのタイムゾーンの時刻で数える。"""
    event = event_for(user, event_id) if event_id else None
    rows = (
        _logs(user, event)
        .filter(local_date__range=(first_day(today), today), occurred_at__isnull=False)
        .values_list("occurred_at", "timezone")
    )
    counts = [0] * len(TIME_SLOTS)
    for at, tz in rows.iterator():
        counts[_slot(at.astimezone(zone(tz)).hour)] += 1
    return _tendency(
        TIME_SLOTS,
        counts,
        few="時刻つきの記録が増えると、よくやる時間帯がわかります",
        even="どの時間帯も同じくらい",
    )


def first_day(today: date) -> date:
    """期間の始まり：今週の日曜から52週前の日曜。"""
    sunday = today - timedelta((today.weekday() + 1) % 7)
    return sunday - timedelta(weeks=WEEKS - 1)


def _logs(user, event: Event | None):
    qs = Log.objects.filter(space__members__user=user)
    return qs.filter(event=event) if event else qs


def year_review(user, today: date, event_id=None) -> YearReview:
    """1年分（53週）の、日ごとの記録の数。ほかの人のイベントで絞ろうとしたら Event.DoesNotExist。"""
    event = event_for(user, event_id) if event_id else None
    start = first_day(today)
    rows = (
        _logs(user, event)
        .filter(local_date__range=(start, today))
        .values("local_date")
        .annotate(logs=Count("id"), kinds=Count("event", distinct=True))
        .order_by("local_date")
    )
    days = {r["local_date"]: DayCount(r["logs"], r["kinds"]) for r in rows}
    return YearReview(start=start, end=today, event=event, days=days)


def logs_on(user, day: date, event_id=None) -> list[Log]:
    """その日の記録。時刻の早い順で、時刻なしの記録は後ろ。"""
    event = event_for(user, event_id) if event_id else None
    qs = _logs(user, event).filter(local_date=day).select_related("event")
    return list(qs.order_by(F("occurred_at").asc(nulls_last=True), "created_at"))
