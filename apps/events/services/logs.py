"""記録の追加・取り消し・編集と、イベントのキャッシュ更新（決定 026・028・032）。"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from apps.events.models import Event, Log
from apps.events.services.access import event_for, log_for
from apps.events.services.dates import now_utc, zone
from apps.events.services.streaks import compute_streak

MEMO_MAX = 1000
FUTURE_GRACE = timedelta(seconds=60)  # 端末とサーバーの時計のずれを許す幅


@dataclass(frozen=True)
class When:
    """いつやったか。date が None なら「今」（時刻あり）。date だけなら時刻なしの記録（決定 012）。"""

    date: date | None = None
    time: time | None = None


def resolve_when(when: When, tz_name: str, now: datetime) -> tuple[date, datetime | None, str]:
    """When を (local_date, occurred_at, timezone) にする。新規の記録と編集で同じ規則を使う。"""
    tz = zone(tz_name)
    today = now.astimezone(tz).date()
    if when.date is None:
        return (today, now, tz.key)
    if when.date > today:
        raise ValidationError("未来の日付は記録できません。今日より前の日付を選んでください", code="future_date")
    if when.time is None:
        return (when.date, None, "")
    occurred = datetime.combine(when.date, when.time, tzinfo=tz)
    if occurred > now + FUTURE_GRACE:
        raise ValidationError("まだ来ていない時刻です。時刻を直すか、空欄にしてください", code="future_time")
    return (when.date, occurred, tz.key)


def clean_memo(memo: str) -> str:
    memo = (memo or "").strip()
    if len(memo) > MEMO_MAX:
        raise ValidationError(f"メモは{MEMO_MAX}文字までです", code="memo_too_long")
    return memo


def refresh_event_cache(event: Event) -> Event:
    """記録から、最終記録日・記録回数・連続記録を計算し直して保存する。"""
    logs = Log.objects.filter(event=event)
    dates = logs.order_by("-local_date").values_list("local_date", flat=True).distinct()
    event.log_count = logs.count()
    event.last_local_date = dates.first()
    event.streak_count, event.streak_period = compute_streak(dates.iterator(), event.streak_unit)
    event.save(update_fields=["log_count", "last_local_date", "streak_count", "streak_period", "updated_at"])
    return event


@dataclass(frozen=True)
class RecordResult:
    log: Log
    event: Event
    created: bool
    streak_before: int

    @property
    def streak_grew(self) -> bool:
        from apps.events.services.streaks import STREAK_MIN

        return self.created and self.event.streak_count > self.streak_before and self.event.streak_count >= STREAK_MIN


def _existing(log_id, event: Event) -> Log | None:
    log = Log.objects.filter(id=log_id).first()
    if log is None:
        return None
    if log.space_id != event.space_id:
        # 他のスペースの ID とぶつかった。存在を知らせないよう「イベントが見つからない」と同じ扱いにする（レビュー 14）
        raise Event.DoesNotExist
    if log.event_id != event.id:
        raise PermissionDenied("この記録 ID は別のイベントで使われています")
    return log


@transaction.atomic
def record(
    user,
    event_id,
    log_id: uuid.UUID,
    when: When | None = None,
    memo: str = "",
    source: str = Log.Source.APP,
    now: datetime | None = None,
) -> RecordResult:
    """記録を追加する。同じ log_id で何度呼んでも1件しか作らない（冪等、決定 028）。"""
    now = now or now_utc()
    event = event_for(user, event_id, lock=True)
    before = event.streak_count
    if (existing := _existing(log_id, event)) is not None:
        return RecordResult(existing, event, False, before)

    local_date, occurred_at, tz_name = resolve_when(when or When(), user.timezone, now)
    try:
        with transaction.atomic():
            log = Log.objects.create(
                id=log_id,
                space_id=event.space_id,
                event=event,
                local_date=local_date,
                occurred_at=occurred_at,
                timezone=tz_name,
                memo=clean_memo(memo),
                source=source,
                created_by=user,
            )
    except IntegrityError:
        # 同じ ID が同時に届いた場合
        return RecordResult(_existing(log_id, event), event, False, before)
    refresh_event_cache(event)
    return RecordResult(log, event, True, before)


@transaction.atomic
def undo(user, log_id) -> Event | None:
    """記録を取り消す（削除）。すでにない場合は何もしない（再送に備えて冪等）。"""
    try:
        log = log_for(user, log_id)
    except Log.DoesNotExist:
        return None
    event = event_for(user, log.event_id, lock=True)
    log.delete()
    return refresh_event_cache(event)


@transaction.atomic
def edit(user, log_id, when: When, memo: str, now: datetime | None = None) -> Log:
    """記録の日付・時刻・メモを変える。日付は編集したときのタイムゾーンで決め直す（決定 026）。"""
    now = now or now_utc()
    log = log_for(user, log_id)
    event = event_for(user, log.event_id, lock=True)
    log.local_date, log.occurred_at, log.timezone = resolve_when(when, user.timezone, now)
    log.memo = clean_memo(memo)
    log.save(update_fields=["local_date", "occurred_at", "timezone", "memo", "updated_at"])
    refresh_event_cache(event)
    return log
