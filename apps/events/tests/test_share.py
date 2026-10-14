"""シェア（SPEC 3.8、決定 017・053）。画像に載せる見出しと投稿文を決める。画像そのものは端末で作る。"""

import uuid
from datetime import timedelta

import pytest

from apps.core.testing import TODAY, new_user
from apps.events.models import Log
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.logs import When
from apps.events.services.share import is_milestone, share_info

SITE = "https://yattalog.example/"


def record(user, event, days_ago=0, memo=""):
    when = When(date=TODAY - timedelta(days_ago)) if days_ago else None
    return log_svc.record(user, event.id, uuid.uuid7(), when, memo).log


@pytest.fixture
def weekly(user):
    return ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week")


def test_はじめての記録は_はじめての記録_と出す(user, weekly):
    assert share_info(user, record(user, weekly).id, SITE).headline == "はじめての記録"


def test_連続記録が続いていれば_それを見出しにして_下に通算の回数を添える(user, weekly):
    for days in (14, 7):
        record(user, weekly, days)
    info = share_info(user, record(user, weekly).id, SITE)
    assert (info.headline, info.subline) == ("🔥 3週連続", "通算 3回目")


def test_連続していなければ_何日ぶりではなく_通算の何回目かを出す(user, weekly):
    """久しぶりの記録を「40日ぶり」と書くと、サボっていたように読める。回数なら、いつでも前向きに読める。"""
    record(user, weekly, 40)
    info = share_info(user, record(user, weekly).id, SITE)
    assert (info.headline, info.subline) == ("2回目", "")


def test_同じ日の2回目も_通算の何回目かを出す(user):
    daily = ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf", streak_unit="none")
    record(user, daily, 3)
    record(user, daily)
    third = record(user, daily)
    assert share_info(user, third.id, SITE).headline == "3回目"


def test_区切りの回数には_お祝いの印を付ける(user):
    dentist = ev_svc.create_event(user, name="歯医者", emoji="🦷", color="pink", streak_unit="none")
    for days in range(30, 21, -1):
        record(user, dentist, days)
    tenth = record(user, dentist, 20)
    eleventh = record(user, dentist, 10)
    assert share_info(user, tenth.id, SITE).headline == "🎉 10回目"
    assert share_info(user, eleventh.id, SITE).headline == "11回目"


@pytest.mark.parametrize(
    ("n", "expected"),
    [(9, False), (10, True), (30, True), (50, True), (100, True), (150, False), (200, True), (1000, True)],
)
def test_区切りは_10_30_50_100回目と_そのあと100回ごと(n, expected):
    assert is_milestone(n) is expected


def test_見出しは_その記録の時点で決める_あとの記録に左右されない(user, weekly):
    old = record(user, weekly, 40)
    record(user, weekly, 7)
    record(user, weekly)

    assert share_info(user, old.id, SITE).headline == "はじめての記録"


def test_回数は_その記録の時点で数える_あとから過去の日付で足した記録は前に数える(user, weekly):
    today = record(user, weekly)
    record(user, weekly, 40)
    assert share_info(user, today.id, SITE).headline == "2回目"


def test_連続の単位が_なし_のイベントも_通算の何回目かを出す(user):
    dentist = ev_svc.create_event(user, name="歯医者", emoji="🦷", color="pink", streak_unit="none")
    record(user, dentist, 180)
    assert share_info(user, record(user, dentist).id, SITE).headline == "2回目"


def test_投稿文は_アイコンと名前と見出しと_ハッシュタグとURL(user, weekly):
    info = share_info(user, record(user, weekly).id, SITE)
    assert info.text == "🛏️ シーツ交換 やった！ はじめての記録 #Yattalog https://yattalog.example/"


def test_連続記録の投稿文には_通算の回数も添える(user, weekly):
    for days in (14, 7):
        record(user, weekly, days)
    info = share_info(user, record(user, weekly).id, SITE)
    assert info.text == "🛏️ シーツ交換 やった！ 🔥 3週連続（通算 3回目） #Yattalog https://yattalog.example/"


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
