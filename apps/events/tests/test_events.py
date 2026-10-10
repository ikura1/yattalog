import uuid
from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError

from apps.events.models import Event
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services import stats
from apps.events.services.logs import When


def names(user, category=None):
    qs = Event.objects.filter(space__members__user=user, is_archived=False).order_by("sort_key")
    if category is not None:
        qs = qs.filter(category=category)
    return [e.name for e in qs]


def make(user, name, category=None):
    return ev_svc.create_event(user, name=name, emoji="⭐", color="sky", category_id=category.id if category else None)


def test_new_events_go_first(user):
    make(user, "A")
    make(user, "B")
    assert names(user) == ["B", "A"]


def test_move_within_category_keeps_others(user):
    house = ev_svc.create_category(user, "家事")
    a = make(user, "a", house)
    make(user, "x")
    make(user, "b", house)
    make(user, "y")
    c = make(user, "c", house)
    # 全体：c y b x a、家事のタブ：c b a
    assert names(user) == ["c", "y", "b", "x", "a"]
    # 家事のタブで a を c の前（先頭）に動かす
    ev_svc.move_event(user, a.id, after_id=c.id)
    assert names(user, house) == ["a", "c", "b"]
    assert [n for n in names(user) if n in "xy"] == ["y", "x"]


def test_delete_category_keeps_events(user):
    house = ev_svc.create_category(user, "家事")
    e = make(user, "a", house)
    ev_svc.delete_category(user, house.id)
    e.refresh_from_db()
    assert e.category is None


def test_cannot_use_other_users_category(user, other_user):
    theirs = ev_svc.create_category(other_user, "趣味")
    with pytest.raises(ValidationError):
        make(user, "a", theirs)


def test_name_required(user):
    with pytest.raises(ValidationError):
        ev_svc.create_event(user, name="  ", emoji="⭐", color="sky")


def test_archive_and_restore_goes_first(user):
    a = make(user, "a")
    make(user, "b")
    ev_svc.set_archived(user, a.id, True)
    assert names(user) == ["b"]
    ev_svc.set_archived(user, a.id, False)
    assert names(user) == ["a", "b"]


def test_stats_and_season(user):
    e = make(user, "布団")
    today = date(2026, 10, 10)
    for d in [date(2026, 4, 1), date(2026, 4, 8), date(2026, 4, 15), date(2026, 5, 1), date(2026, 9, 1)]:
        log_svc.record(user, e.id, uuid.uuid7(), When(date=d))
    e.refresh_from_db()
    s = stats.event_stats(e, today)
    assert s.total == 5 and s.this_year == 5 and s.pace == "だいたい5週間ごと"
    season = stats.season(e, 2026)
    assert season.counts[3] == 3 and season.headline == "よくやるのは 4月"
    assert stats.season(e, None).years == [2026]


def test_pace_needs_two_days(user):
    e = make(user, "a")
    log_svc.record(user, e.id, uuid.uuid7(), When(date=date(2026, 1, 1) - timedelta(0)))
    e.refresh_from_db()
    assert stats.event_stats(e, date(2026, 10, 10)).pace is None
