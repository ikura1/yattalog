"""タイムゾーンの設定（決定 023）。"""

import pytest
from django.core.exceptions import ValidationError

from apps.accounts.services import set_timezone
from apps.core.testing import NOW


def test_はじめての設定で_タイムゾーンが決まり_使い始めた時刻が入る(user):
    set_timezone(user, "America/Los_Angeles", keep=False, now=NOW)
    user.refresh_from_db()
    assert (user.timezone, user.onboarded_at) == ("America/Los_Angeles", NOW)


def test_このまま_を選ぶと_タイムゾーンは変えず_その端末の値を覚える(user):
    set_timezone(user, "America/Los_Angeles", keep=True, now=NOW)
    user.refresh_from_db()
    assert (user.timezone, user.timezone_kept_for) == ("Asia/Tokyo", "America/Los_Angeles")


def test_使い始めた時刻は_2回目からは変わらない(user):
    from datetime import timedelta

    set_timezone(user, "Asia/Tokyo", keep=False, now=NOW)
    set_timezone(user, "Europe/London", keep=False, now=NOW + timedelta(days=1))
    user.refresh_from_db()
    assert (user.timezone, user.onboarded_at) == ("Europe/London", NOW)


def test_正しくないタイムゾーンは_受け付けない(user):
    with pytest.raises(ValidationError, match="タイムゾーン"):
        set_timezone(user, "No/Such_Zone", keep=False, now=NOW)
    user.refresh_from_db()
    assert user.timezone == "Asia/Tokyo" and user.onboarded_at is None
