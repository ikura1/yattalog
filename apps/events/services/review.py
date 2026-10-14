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


def logs_on(user, day: date, event_id=None) -> list[Log]:
    """その日の記録。時刻の早い順で、時刻なしの記録は後ろ。"""
    event = event_for(user, event_id) if event_id else None
    qs = _logs(user, event).filter(local_date=day).select_related("event")
    return list(qs.order_by(F("occurred_at").asc(nulls_last=True), "created_at"))
