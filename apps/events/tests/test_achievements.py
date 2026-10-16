"""実績バッジ（SPEC 3.10、決定 020・063）。解除したら知らせ、一度解除したら消さない。"""

import uuid
from datetime import date, timedelta

import pytest

from apps.core.testing import TODAY, new_user
from apps.events.services import achievements as ach
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.logs import When


def make(user, name="水やり", unit="none"):
    return ev_svc.create_event(user, name=name, emoji="🪴", color="leaf", streak_unit=unit)


def rec(user, event, day=None, memo=""):
    when = When(date=day) if day else None
    return log_svc.record(user, event.id, uuid.uuid7(), when, memo).log


def codes(found):
    return [a.code for a in found]


def test_はじめて記録すると_はじめの一歩が解除されて_知らせる対象になる(user):
    log = rec(user, make(user))
    assert codes(ach.check(user, log)) == ["first"]


def test_同じ実績は_2度は知らせない(user):
    e = make(user)
    ach.check(user, rec(user, e))
    assert ach.check(user, rec(user, e)) == []


def test_全部のイベントの合計10回で_じゅっかい(user):
    a, b = make(user, "a"), make(user, "b")
    for i in range(5):
        rec(user, a, TODAY - timedelta(i))
        rec(user, b, TODAY - timedelta(i))
    assert "t10" in codes(ach.check(user))


def test_連続記録の目標は_単位ごとに違う_毎週なら4週で_つづいてる(user):
    weekly = make(user, "シーツ交換", "week")
    for w in (21, 14, 7):
        rec(user, weekly, TODAY - timedelta(w))
    assert "s1" not in codes(ach.check(user))
    assert "s1" in codes(ach.check(user, rec(user, weekly)))


def test_1つのイベントを50回で_おなじみ(user):
    e = make(user)
    for i in range(50):
        rec(user, e, TODAY - timedelta(i))
    found = codes(ach.check(user))
    assert "e50" in found and "e100" not in found


def test_イベントを10個作ると_コレクター(user):
    for i in range(9):
        make(user, f"e{i}")
    assert "collector" not in codes(ach.check(user))
    make(user, "e9")
    assert "collector" in codes(ach.check(user))


def test_過去の日付で記録すると_思い出した(user):
    e = make(user)
    ach.check(user, rec(user, e))
    assert codes(ach.check(user, rec(user, e, TODAY - timedelta(3)))) == ["past"]


def test_メモつきで10回記録すると_メモ魔(user):
    e = make(user)
    for i in range(10):
        rec(user, e, TODAY - timedelta(i), memo="ベランダも")
    assert "memo" in codes(ach.check(user))


def test_前回から365日以上空けて記録すると_ひさしぶり(user):
    e = make(user)
    rec(user, e, TODAY - timedelta(400))
    ach.check(user)
    assert "longgap" in codes(ach.check(user, rec(user, e)))


def test_364日しか空いていなければ_ひさしぶりにならない(user):
    e = make(user)
    rec(user, e, TODAY - timedelta(364))
    ach.check(user)
    assert "longgap" not in codes(ach.check(user, rec(user, e)))


def test_1日に5種類のイベントを記録すると_大忙し(user):
    for i in range(5):
        rec(user, make(user, f"e{i}"))
    assert "busy" in codes(ach.check(user))


def test_記録を消しても_解除した実績は残る(user):
    e = make(user)
    log = rec(user, e)
    ach.check(user, log)
    log_svc.undo(user, log.id)
    assert [a.code for a, at in ach.listing(user) if at] == ["first"]


def test_実績はほかの人の記録では解除されない(user):
    other = new_user(email="b@example.com")
    rec(other, make(other))
    assert ach.check(user) == []


def test_機能が入る前から使っている人は_最初の判定でまとめて静かに解除する(user):
    """一度に10個以上の知らせが出ないように（決定 063）。"""
    user.achievements_synced = False
    user.save()
    e = make(user)
    for i in range(12):
        rec(user, e, TODAY - timedelta(i), memo="メモ")

    assert ach.check(user, rec(user, e)) == []

    user.refresh_from_db()
    assert user.achievements_synced
    assert {"first", "t10", "memo", "past"} <= {a.code for a, at in ach.listing(user) if at}


def test_シェアしたと端末から知らせを受けると_シェアデビュー(user):
    assert codes(ach.unlock_share(user)) == ["share"]
    assert ach.unlock_share(user) == []


def test_一覧は_定義の順に_解除した日時つきで出し_写真の実績はまだ出さない(user):
    ach.check(user, rec(user, make(user)))
    listing = ach.listing(user)
    assert [a.code for a, _ in listing][:4] == ["first", "t10", "t100", "t1000"]
    assert all(a.code != "photo" for a, _ in listing)
    unlocked = {a.code: at for a, at in listing if at}
    assert list(unlocked) == ["first"] and unlocked["first"] is not None


@pytest.mark.parametrize(
    ("unit", "count", "expected"),
    [("day", 7, "s1"), ("week", 12, "s2"), ("month", 12, "s3"), ("month", 2, None)],
)
def test_連続記録の目標(unit, count, expected):
    assert ach.streak_level(unit, count) == expected


def test_日付だけの記録でも_今日の記録は_思い出したにならない(user):
    e = make(user)
    log = log_svc.record(user, e.id, uuid.uuid7(), When(date=date(2026, 10, 10))).log
    assert "past" not in codes(ach.check(user, log))
