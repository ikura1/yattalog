"""ふりかえり（1年の草、決定 058）。全部のイベントをまたいで、日ごとに何をやったかを数える。

濃さには、その日にやったイベントの「種類の数」を使う。ほとんどのイベントは1日に1回なので、
回数では差が出ない。やらなかった日やストリークの途切れは、数えも見せもしない。
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from django.db.models import Count, F

from apps.events.models import Event, Log
from apps.events.services.access import event_for

WEEKS = 53  # 今週を含めて53週（GitHub の草と同じ）


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


DAY_LIMIT = 200  # その日の記録を、この件数まで出す


class DayLogs(list):
    """その日の記録（上限まで）。more は、上限を超えて出していない件数。"""

    more = 0


def logs_on(user, day: date, event_id=None) -> DayLogs:
    """その日の記録。時刻の早い順で、時刻なしの記録は後ろ。多すぎるときは上限まで。"""
    event = event_for(user, event_id) if event_id else None
    qs = _logs(user, event).filter(local_date=day).select_related("event")
    logs = DayLogs(qs.order_by(F("occurred_at").asc(nulls_last=True), "created_at")[: DAY_LIMIT + 1])
    if len(logs) > DAY_LIMIT:
        logs.more = qs.count() - DAY_LIMIT
        del logs[DAY_LIMIT:]
    return logs


# --- 1年前の今ごろ（決定 061） -----------------------------------------------------------

AROUND = 3  # 1年前の前後何日までを「今ごろ」とするか


@dataclass(frozen=True)
class YearAgo:
    event: Event
    dates: list[date]  # その期間にやった日（古い順。同じ日に何回やっても1つ）


def one_year_before(day: date) -> date:
    """1年前の同じ日。2月29日は、前の年の2月28日にする。"""
    try:
        return day.replace(year=day.year - 1)
    except ValueError:
        return day.replace(year=day.year - 1, day=28)


def a_year_ago(user, today: date, event_id=None) -> list[YearAgo]:
    """1年前の前後3日にやったこと。多くやったイベントから順に。"""
    event = event_for(user, event_id) if event_id else None
    center = one_year_before(today)
    rows = (
        _logs(user, event)
        .filter(local_date__range=(center - timedelta(AROUND), center + timedelta(AROUND)))
        .select_related("event")
        .order_by("local_date", "created_at")
    )
    dates: dict[Event, list[date]] = {}
    counts: dict[Event, int] = {}
    for log in rows:  # 最初にやった順に並ぶ
        days = dates.setdefault(log.event, [])
        if log.local_date not in days:
            days.append(log.local_date)
        counts[log.event] = counts.get(log.event, 0) + 1
    ordered = sorted(dates, key=lambda e: -counts[e])  # 回数の多い順。同じなら、最初にやった順のまま
    return [YearAgo(event=e, dates=dates[e]) for e in ordered]


# --- この1年でよくやったこと（決定 062） ---------------------------------------------------

TOP = 3


@dataclass(frozen=True)
class TopEvent:
    event: Event
    count: int


def top_events(user, today: date) -> list[TopEvent]:
    """草と同じ1年分（53週）で、回数の多いイベントを3つ。"""
    rows = (
        _logs(user, None)
        .filter(local_date__range=(first_day(today), today))
        .values("event")
        .annotate(n=Count("id"))
        .order_by("-n", "event__sort_key")[:TOP]
    )
    rows = list(rows)
    events = Event.objects.in_bulk([r["event"] for r in rows])
    return [TopEvent(event=events[r["event"]], count=r["n"]) for r in rows]
