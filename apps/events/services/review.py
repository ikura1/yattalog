"""ふりかえり（1年の草、決定 058）。全部のイベントをまたいで、日ごとに何をやったかを数える。

濃さには、その日にやったイベントの「種類の数」を使う。ほとんどのイベントは1日に1回なので、
回数では差が出ない。やらなかった日やストリークの途切れは、数えも見せもしない。
"""

from dataclasses import dataclass, field
from datetime import date

from django.db.models import Count, F

from apps.events.models import Event, Log
from apps.events.services.access import event_for

MONTHS = 12  # 今月を含めて、12か月分を出す


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


def first_month(today: date) -> date:
    """期間の始まり：今月を含めて12か月前の月の1日。"""
    m = today.year * 12 + today.month - MONTHS
    return date(m // 12, m % 12 + 1, 1)


def _logs(user, event: Event | None):
    qs = Log.objects.filter(space__members__user=user)
    return qs.filter(event=event) if event else qs


def year_review(user, today: date, event_id=None) -> YearReview:
    """12か月分の、日ごとの記録の数。ほかの人のイベントで絞ろうとしたら Event.DoesNotExist。"""
    event = event_for(user, event_id) if event_id else None
    start = first_month(today)
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
