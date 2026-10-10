"""記録の追加・取り消し・編集と、イベントのキャッシュ更新（決定 026・028・032）。"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from apps.events.models import Event, Log
from apps.events.services.dates import now_utc, today_in, zone
from apps.events.services.streaks import compute_streak

MEMO_MAX = 1000
FUTURE_GRACE = timedelta(seconds=60)  # 端末とサーバーの時計のずれを許す幅


def get_event_for(user, event_id) -> Event:
    """ユーザーがメンバーであるスペースのイベントだけを返す。それ以外は 404 相当（レビュー S4）。"""
    try:
        return Event.objects.select_for_update(of=("self",)).get(id=event_id, space__members__user=user)
    except Event.DoesNotExist, ValueError, ValidationError:
        raise Event.DoesNotExist from None


def get_log_for(user, log_id) -> Log:
    try:
        return Log.objects.select_related("event").get(id=log_id, space__members__user=user)
    except Log.DoesNotExist, ValueError, ValidationError:
        raise Log.DoesNotExist from None


@dataclass(frozen=True)
class When:
    """いつやったか。date だけなら時刻なしの記録になる（決定 012）。"""

    date: date | None = None  # None は「今」
    time: time | None = None


def _resolve_when(when: When, tz_name: str, now: datetime) -> tuple[date, datetime | None, str]:
    tz = zone(tz_name)
    today = now.astimezone(tz).date()
    if when.date is None:
        return (today, now, tz_name)
    if when.date > today:
        raise ValidationError("未来の日付は記録できません。今日より前の日付を選んでください", code="future_date")
    if when.time is None:
        return (when.date, None, "")
    occurred = datetime.combine(when.date, when.time, tzinfo=tz)
    if occurred > now + FUTURE_GRACE:
        raise ValidationError("まだ来ていない時刻です。時刻を直すか、空欄にしてください", code="future_time")
    return (when.date, occurred, tz_name)


def _clean_memo(memo: str) -> str:
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
    created: bool
    streak_before: int
    streak_after: int


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
    event = get_event_for(user, event_id)

    existing = Log.objects.filter(id=log_id).first()
    if existing is not None:
        if existing.event_id != event.id:
            # 他のイベント（他人のものを含む）の ID とぶつかった。端末側の不具合か改ざんなので拒否する
            raise PermissionDenied("この記録 ID は使えません")
        return RecordResult(existing, False, event.streak_count, event.streak_count)

    local_date, occurred_at, tz_name = _resolve_when(when or When(), user.timezone, now)
    before = event.streak_count
    try:
        with transaction.atomic():
            log = Log.objects.create(
                id=log_id,
                space_id=event.space_id,
                event=event,
                local_date=local_date,
                occurred_at=occurred_at,
                timezone=tz_name,
                memo=_clean_memo(memo),
                source=source,
                created_by=user,
            )
    except IntegrityError:
        # 同時に同じ ID が届いた場合
        log = Log.objects.get(id=log_id)
        if log.event_id != event.id:
            raise PermissionDenied("この記録 ID は使えません") from None
        return RecordResult(log, False, before, event.streak_count)
    refresh_event_cache(event)
    return RecordResult(log, True, before, event.streak_count)


@transaction.atomic
def undo(user, log_id) -> Event | None:
    """記録を取り消す（削除）。すでにない場合は何もしない（再送に備えて冪等）。"""
    try:
        log = get_log_for(user, log_id)
    except Log.DoesNotExist:
        return None
    event = Event.objects.select_for_update().get(id=log.event_id)
    log.delete()
    return refresh_event_cache(event)


@transaction.atomic
def edit(user, log_id, when: When, memo: str, now: datetime | None = None) -> Log:
    """記録の日付・時刻・メモを変える。日付は編集したときのタイムゾーンで決め直す（決定 026）。"""
    now = now or now_utc()
    log = get_log_for(user, log_id)
    event = Event.objects.select_for_update().get(id=log.event_id)
    if when.date is None:
        when = When(date=today_in(user.timezone, now), time=None)
    log.local_date, log.occurred_at, log.timezone = _resolve_when(when, user.timezone, now)
    log.memo = _clean_memo(memo)
    log.save(update_fields=["local_date", "occurred_at", "timezone", "memo", "updated_at"])
    refresh_event_cache(event)
    return log


def add_memo(user, log_id, memo: str) -> Log:
    log = get_log_for(user, log_id)
    log.memo = _clean_memo(memo)
    log.save(update_fields=["memo", "updated_at"])
    return log
