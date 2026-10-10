import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from apps.events.models import Event, Log
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.logs import When

NOW = datetime(2026, 10, 10, 3, 0, tzinfo=UTC)  # 日本時間 12:00
TODAY = date(2026, 10, 10)


@pytest.fixture
def event(user):
    return ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week")


def test_record_now_uses_users_timezone(user, event):
    r = log_svc.record(user, event.id, uuid.uuid7(), now=NOW)
    assert r.created and r.log.local_date == TODAY and r.log.timezone == "Asia/Tokyo"
    event.refresh_from_db()
    assert event.last_local_date == TODAY and event.log_count == 1


def test_record_is_idempotent(user, event):
    lid = uuid.uuid7()
    a = log_svc.record(user, event.id, lid, now=NOW)
    b = log_svc.record(user, event.id, lid, now=NOW)
    assert a.created and not b.created
    assert Log.objects.count() == 1


def test_cannot_reuse_another_users_log_id(user, other_user, event):
    other_event = ev_svc.create_event(other_user, name="散髪", emoji="✂️", color="grape")
    lid = uuid.uuid7()
    log_svc.record(other_user, other_event.id, lid, now=NOW)
    with pytest.raises(PermissionDenied):
        log_svc.record(user, event.id, lid, now=NOW)


def test_cannot_record_to_another_users_event(user, other_user):
    other_event = ev_svc.create_event(other_user, name="散髪", emoji="✂️", color="grape")
    with pytest.raises(Event.DoesNotExist):
        log_svc.record(user, other_event.id, uuid.uuid7(), now=NOW)


def test_cannot_undo_another_users_log(user, other_user):
    other_event = ev_svc.create_event(other_user, name="散髪", emoji="✂️", color="grape")
    lid = uuid.uuid7()
    log_svc.record(other_user, other_event.id, lid, now=NOW)
    assert log_svc.undo(user, lid) is None
    assert Log.objects.filter(id=lid).exists()


def test_past_date_without_time(user, event):
    r = log_svc.record(user, event.id, uuid.uuid7(), When(date=TODAY - timedelta(1)), now=NOW)
    assert r.log.local_date == TODAY - timedelta(1) and r.log.occurred_at is None and r.log.timezone == ""


def test_future_date_is_rejected(user, event):
    with pytest.raises(ValidationError):
        log_svc.record(user, event.id, uuid.uuid7(), When(date=TODAY + timedelta(1)), now=NOW)


def test_future_time_today_is_rejected(user, event):
    with pytest.raises(ValidationError):
        log_svc.record(user, event.id, uuid.uuid7(), When(date=TODAY, time=time(23, 0)), now=NOW)


def test_local_date_does_not_change_when_timezone_changes(user, event):
    r = log_svc.record(user, event.id, uuid.uuid7(), now=NOW)
    user.timezone = "America/Los_Angeles"
    user.save()
    r.log.refresh_from_db()
    assert r.log.local_date == TODAY  # 決定 026


def test_undo_recomputes_cache(user, event):
    a = log_svc.record(user, event.id, uuid.uuid7(), When(date=TODAY - timedelta(7)), now=NOW)
    b = log_svc.record(user, event.id, uuid.uuid7(), now=NOW)
    event.refresh_from_db()
    assert event.streak_count == 2 and b.streak_after == 2 and a.created
    log_svc.undo(user, b.log.id)
    event.refresh_from_db()
    assert event.log_count == 1 and event.last_local_date == TODAY - timedelta(7) and event.streak_count == 1


def test_edit_changes_date(user, event):
    r = log_svc.record(user, event.id, uuid.uuid7(), now=NOW)
    log_svc.edit(user, r.log.id, When(date=TODAY - timedelta(3), time=time(9, 30)), "メモ", now=NOW)
    r.log.refresh_from_db()
    assert r.log.local_date == TODAY - timedelta(3) and r.log.memo == "メモ" and r.log.occurred_at is not None


def test_memo_too_long(user, event):
    with pytest.raises(ValidationError):
        log_svc.record(user, event.id, uuid.uuid7(), memo="あ" * 1001, now=NOW)


def test_create_event_with_last_done(user):
    e = ev_svc.create_event(user, name="散髪", emoji="✂️", color="grape", last_done=TODAY - timedelta(32))
    assert e.last_local_date == TODAY - timedelta(32) and e.log_count == 1


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.lists(st.tuples(st.booleans(), st.integers(min_value=0, max_value=60)), min_size=1, max_size=25))
def test_cache_matches_recompute(user, ops):
    """追加と取り消しをランダムに繰り返しても、キャッシュは一から計算した値と一致する。"""
    event = ev_svc.create_event(user, name="ジム", emoji="🏋️", color="sun", streak_unit="day")
    ids: list[uuid.UUID] = []
    for add, back in ops:
        if add or not ids:
            lid = uuid.uuid7()
            log_svc.record(user, event.id, lid, When(date=TODAY - timedelta(back)), now=NOW)
            ids.append(lid)
        else:
            log_svc.undo(user, ids.pop(back % len(ids)))
    event.refresh_from_db()
    cached = (event.log_count, event.last_local_date, event.streak_count, event.streak_period)
    log_svc.refresh_event_cache(event)
    event.refresh_from_db()
    assert cached == (event.log_count, event.last_local_date, event.streak_count, event.streak_period)
