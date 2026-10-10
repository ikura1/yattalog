"""記録の追加・取り消し・編集（決定 026・028）。"""

import uuid
from datetime import time, timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from apps.events.models import Event, Log
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.logs import When
from conftest import NOW, TODAY, new_user


@pytest.fixture
def event(user):
    return ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week")


def test_今の記録はユーザーのタイムゾーンでの日付と時刻を持つ(user, event):
    r = log_svc.record(user, event.id, uuid.uuid7())
    assert (r.log.local_date, r.log.occurred_at, r.log.timezone) == (TODAY, NOW, "Asia/Tokyo")


def test_記録するとイベントの最終記録日と回数が更新される(user, event):
    log_svc.record(user, event.id, uuid.uuid7())
    event.refresh_from_db()
    assert (event.last_local_date, event.log_count) == (TODAY, 1)


def test_同じIDで2回送っても記録は1件(user, event):
    lid = uuid.uuid7()
    first = log_svc.record(user, event.id, lid)
    second = log_svc.record(user, event.id, lid)
    assert (first.created, second.created) == (True, False)
    assert Log.objects.count() == 1


def test_同じIDを自分の別のイベントで使うと拒否される(user, event):
    other = ev_svc.create_event(user, name="散髪", emoji="✂️", color="grape")
    lid = uuid.uuid7()
    log_svc.record(user, event.id, lid)
    with pytest.raises(PermissionDenied):
        log_svc.record(user, other.id, lid)


def test_他人の記録IDとぶつかってもIDの存在は分からない(user, other_user, event):
    theirs = ev_svc.create_event(other_user, name="散髪", emoji="✂️", color="grape")
    lid = uuid.uuid7()
    log_svc.record(other_user, theirs.id, lid)
    with pytest.raises(Event.DoesNotExist):  # 「イベントが見つからない」と同じ扱い（レビュー 14）
        log_svc.record(user, event.id, lid)


def test_他人のイベントには記録できない(user, other_user):
    theirs = ev_svc.create_event(other_user, name="散髪", emoji="✂️", color="grape")
    with pytest.raises(Event.DoesNotExist):
        log_svc.record(user, theirs.id, uuid.uuid7())


def test_他人の記録は取り消せない(user, other_user):
    theirs = ev_svc.create_event(other_user, name="散髪", emoji="✂️", color="grape")
    lid = uuid.uuid7()
    log_svc.record(other_user, theirs.id, lid)
    assert log_svc.undo(user, lid) is None
    assert Log.objects.filter(id=lid).exists()


def test_過去の日付だけを指定すると時刻なしの記録になる(user, event):
    r = log_svc.record(user, event.id, uuid.uuid7(), When(date=TODAY - timedelta(1)))
    assert (r.log.local_date, r.log.occurred_at, r.log.timezone) == (TODAY - timedelta(1), None, "")


def test_未来の日付は記録できない(user, event):
    with pytest.raises(ValidationError):
        log_svc.record(user, event.id, uuid.uuid7(), When(date=TODAY + timedelta(1)))


def test_今日のまだ来ていない時刻は記録できない(user, event):
    with pytest.raises(ValidationError):
        log_svc.record(user, event.id, uuid.uuid7(), When(date=TODAY, time=time(23, 0)))


def test_タイムゾーンを変えても記録の日付は変わらない(user, event):
    r = log_svc.record(user, event.id, uuid.uuid7())
    user.timezone = "America/Los_Angeles"
    user.save()
    r.log.refresh_from_db()
    assert r.log.local_date == TODAY  # 決定 026


def test_取り消すと最終記録日と連続記録が計算し直される(user, event):
    log_svc.record(user, event.id, uuid.uuid7(), When(date=TODAY - timedelta(7)))
    latest = log_svc.record(user, event.id, uuid.uuid7())
    log_svc.undo(user, latest.log.id)
    event.refresh_from_db()
    assert (event.log_count, event.last_local_date, event.streak_count) == (1, TODAY - timedelta(7), 1)


def test_編集で日付と時刻とメモを変えられる(user, event):
    r = log_svc.record(user, event.id, uuid.uuid7())
    log_svc.edit(user, r.log.id, When(date=TODAY - timedelta(3), time=time(9, 30)), "メモ")
    r.log.refresh_from_db()
    assert (r.log.local_date, r.log.occurred_at.hour, r.log.memo) == (
        TODAY - timedelta(3),
        0,
        "メモ",
    )  # 9:30 JST = 0:30 UTC


def test_編集で今を選ぶと時刻ありの記録になる(user, event):
    r = log_svc.record(user, event.id, uuid.uuid7(), When(date=TODAY - timedelta(2)))
    log_svc.edit(user, r.log.id, When(), "")
    r.log.refresh_from_db()
    assert (r.log.local_date, r.log.occurred_at) == (TODAY, NOW)


def test_メモは1000文字まで(user, event):
    with pytest.raises(ValidationError):
        log_svc.record(user, event.id, uuid.uuid7(), memo="あ" * 1001)


def test_前回やった日を入れてイベントを作ると時刻なしの記録が1件できる(user):
    e = ev_svc.create_event(user, name="散髪", emoji="✂️", color="grape", last_done=TODAY - timedelta(32))
    assert (e.last_local_date, e.log_count) == (TODAY - timedelta(32), 1)


def test_DBの制約で時刻とタイムゾーンは必ず一緒に入る(user, event):
    with pytest.raises(IntegrityError):
        Log.objects.create(id=uuid.uuid7(), space=event.space, event=event, local_date=TODAY, occurred_at=NOW)


@pytest.mark.django_db
@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])  # DB を使うので CI では遅い
@given(st.lists(st.tuples(st.booleans(), st.integers(min_value=0, max_value=60)), min_size=1, max_size=25))
def test_追加と取り消しを繰り返してもキャッシュは一から計算した値と一致する(ops):
    # 例ごとに新しいユーザーを作り、例どうしで状態を共有しない（レビュー 6）
    user = new_user(email=f"{uuid.uuid4()}@example.com")
    event = ev_svc.create_event(user, name="ジム", emoji="🏋️", color="sun", streak_unit="day")
    ids: list[uuid.UUID] = []
    for add, back in ops:
        if add or not ids:
            lid = uuid.uuid7()
            log_svc.record(user, event.id, lid, When(date=TODAY - timedelta(back)))
            ids.append(lid)
        else:
            log_svc.undo(user, ids.pop(back % len(ids)))
    event.refresh_from_db()
    cached = (event.log_count, event.last_local_date, event.streak_count, event.streak_period)
    log_svc.refresh_event_cache(event)
    event.refresh_from_db()
    assert cached == (event.log_count, event.last_local_date, event.streak_count, event.streak_period)
