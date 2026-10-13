"""シェア（SPEC 3.8、決定 017・053）。画像に載せる見出しと投稿文を決める。画像そのものは端末で作る。"""

import uuid
from datetime import timedelta

import pytest

from apps.core.testing import TODAY, new_user
from apps.events.models import Log
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.logs import When
from apps.events.services.share import share_info

SITE = "https://yattalog.example/"


def record(user, event, days_ago=0, memo=""):
    when = When(date=TODAY - timedelta(days_ago)) if days_ago else None
    return log_svc.record(user, event.id, uuid.uuid7(), when, memo).log


@pytest.fixture
def weekly(user):
    return ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week")


def test_はじめての記録は_はじめての記録_と出す(user, weekly):
    assert share_info(user, record(user, weekly).id, SITE).headline == "はじめての記録"


def test_連続記録が続いていれば_それを見出しにする(user, weekly):
    for days in (14, 7):
        record(user, weekly, days)
    info = share_info(user, record(user, weekly).id, SITE)
    assert info.headline == "🔥 3週連続"


def test_連続していなければ_何日ぶりかを出す(user, weekly):
    record(user, weekly, 40)
    assert share_info(user, record(user, weekly).id, SITE).headline == "40日ぶり"


def test_同じ日の2回目は_今日2回目_ではなく_その日の何回目かを出す(user):
    daily = ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf", streak_unit="none")
    record(user, daily)
    second = record(user, daily)
    assert share_info(user, second.id, SITE).headline == "この日2回目"


def test_見出しは_その記録の時点で決める_あとの記録に左右されない(user, weekly):
    old = record(user, weekly, 40)
    record(user, weekly, 7)
    record(user, weekly)

    assert share_info(user, old.id, SITE).headline == "はじめての記録"


def test_連続の単位が_なし_のイベントは_何日ぶりかを出す(user):
    dentist = ev_svc.create_event(user, name="歯医者", emoji="🦷", color="pink", streak_unit="none")
    record(user, dentist, 180)
    assert share_info(user, record(user, dentist).id, SITE).headline == "180日ぶり"


def test_投稿文は_アイコンと名前と見出しと_ハッシュタグとURL(user, weekly):
    info = share_info(user, record(user, weekly).id, SITE)
    assert info.text == "🛏️ シーツ交換 やった！ はじめての記録 #Yattalog https://yattalog.example/"


def test_画像に載せる日時は_記録したときのタイムゾーンで出す(user, weekly):
    timed = share_info(user, record(user, weekly).id, SITE)
    dateonly = share_info(user, record(user, weekly, 3).id, SITE)
    assert (timed.when, dateonly.when) == ("2026年10月10日 12:00", "2026年10月7日")


def test_メモは持っているが_載せるかどうかは画面で選ぶ(user, weekly):
    info = share_info(user, record(user, weekly, memo="冬用に替えた").id, SITE)
    assert info.memo == "冬用に替えた" and "冬用" not in info.text


def test_ほかの人の記録は_シェアできない(user, weekly):
    other = new_user(email="b@example.com")
    theirs = ev_svc.create_event(other, name="ひみつ", emoji="🤫", color="pink")
    log = record(other, theirs)
    with pytest.raises(Log.DoesNotExist):
        share_info(user, log.id, SITE)
