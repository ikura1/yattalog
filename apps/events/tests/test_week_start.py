"""週の始まり（月曜／日曜）。連続記録の区切りと、カレンダー・草・曜日の並びをそろえる（決定 066）。"""

import uuid
from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.dates import period_index
from apps.events.services.logs import When
from apps.events.services.streaks import compute_streak
from apps.spaces.services import personal_space

SAT, SUN, MON = date(2026, 10, 10), date(2026, 10, 11), date(2026, 10, 12)


def test_月曜始まりでは_日曜と月曜で週が変わる():
    assert period_index(SAT, "week", "mon") == period_index(SUN, "week", "mon") != period_index(MON, "week", "mon")


def test_日曜始まりでは_土曜と日曜で週が変わる():
    assert period_index(SAT, "week", "sun") != period_index(SUN, "week", "sun") == period_index(MON, "week", "sun")


def test_既定は月曜始まり_決定015():
    assert period_index(SUN, "week") == period_index(SUN, "week", "mon")


def test_連続記録は_週の始まりで数え方が変わる():
    dates = [date(2026, 10, 10), date(2026, 10, 4)]  # 土曜と、その前の日曜
    assert compute_streak(dates, "week", "mon")[0] == 2  # 月曜始まりなら別の週が2つ続く
    assert compute_streak(dates, "week", "sun")[0] == 1  # 日曜始まりなら同じ週


def test_スペースの週の始まりは_既定で月曜(user):
    assert personal_space(user).week_start == "mon"


def test_週の始まりを変えると_そのスペースのイベントの連続記録を数え直す(user):
    e = ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week")
    for d in (date(2026, 10, 4), date(2026, 10, 10)):
        log_svc.record(user, e.id, uuid.uuid7(), When(date=d))
    e.refresh_from_db()
    assert e.streak_count == 2

    ev_svc.set_week_start(user, "sun")

    e.refresh_from_db()
    assert personal_space(user).week_start == "sun" and e.streak_count == 1


def test_週の始まりに知らない値は入れられない(user):
    with pytest.raises(ValidationError):
        ev_svc.set_week_start(user, "wed")


# --- 画面の並びも、週の始まりにそろえる ---


def test_ふりかえりの1年は_週の始まりの曜日から数える(user):
    from apps.events.services.review import first_day, year_review

    # 2026-10-10 は土曜。月曜始まりなら今週は 10-05（月）から、日曜始まりなら 10-04（日）から
    assert first_day(SAT, "mon") == date(2025, 10, 6)
    assert first_day(SAT, "sun") == date(2025, 10, 5)
    assert year_review(user, SAT).start == date(2025, 10, 6)
    ev_svc.set_week_start(user, "sun")
    assert year_review(user, SAT).start == date(2025, 10, 5)


def test_よくやる曜日は_週の始まりの曜日から並べる(user):
    from apps.events.services import stats

    e = ev_svc.create_event(user, name="ジム", emoji="🏋️", color="tomato")
    for d in (date(2026, 10, 4), date(2026, 9, 27), date(2026, 10, 5)):  # 日・日・月
        log_svc.record(user, e.id, uuid.uuid7(), When(date=d))
    e.refresh_from_db()
    t = stats.weekday_tendency(e)
    assert (t.names[0], t.counts[0], t.counts[-1]) == ("月", 1, 2)
    ev_svc.set_week_start(user, "sun")
    e.refresh_from_db()
    t = stats.weekday_tendency(e)
    assert (t.names[0], t.counts[0]) == ("日", 2)
