"""はじめて使うときのテンプレート（SPEC 3.6、決定 009・042）。"""

import pytest
from django.core.exceptions import ValidationError

from apps.core.testing import new_user
from apps.events.models import COLORS, Category, Event, StreakUnit
from apps.events.services import events as ev_svc
from apps.events.services.events import is_single_emoji
from apps.events.services.starter import STARTERS, add_starters, starter_choices


def test_テンプレートは_そのままイベントとして作れる内容になっている():
    assert len(STARTERS) == len({s.key for s in STARTERS}) == len({s.name for s in STARTERS}) >= 10
    for s in STARTERS:
        assert is_single_emoji(s.emoji) and s.color in COLORS and s.streak_unit in StreakUnit.values
        assert 0 < len(s.name) <= 40 and s.category in {"家事", "身の回り", "趣味"}


def test_選んだテンプレートが_アイコンと色と単位とカテゴリつきで追加される(user):
    add_starters(user, ["sheets", "haircut"])

    got = {e.name: (e.emoji, e.color, e.streak_unit, e.category.name) for e in Event.objects.select_related("category")}
    assert got == {
        "シーツ交換": ("🛏️", "sky", "week", "家事"),
        "散髪": ("✂️", "grape", "month", "身の回り"),
    }


def test_必要なカテゴリだけが作られ_同じカテゴリは1つにまとまる(user):
    add_starters(user, ["sheets", "car-wash", "haircut"])
    assert list(Category.objects.order_by("sort_key").values_list("name", flat=True)) == ["家事", "身の回り"]


def test_すでにあるカテゴリは_そのまま使う(user):
    mine = ev_svc.create_category(user, "家事", emoji="🧹")
    add_starters(user, ["sheets"])
    assert Category.objects.count() == 1 and Event.objects.get().category == mine


def test_ホームには_テンプレートの一覧と同じ順で並ぶ(user):
    keys = ["haircut", "sheets", "gym"]
    add_starters(user, keys)
    order = [s.name for s in STARTERS if s.key in keys]
    assert list(Event.objects.order_by("sort_key").values_list("name", flat=True)) == order


def test_同じ名前のイベントがすでにあるテンプレートは_追加しない(user):
    ev_svc.create_event(user, name="散髪", emoji="💇", color="pink")

    added = add_starters(user, ["sheets", "haircut"])

    assert [e.name for e in added] == ["シーツ交換"]
    assert Event.objects.filter(name="散髪").count() == 1


def test_何も選ばなければ_追加せずに知らせる(user):
    with pytest.raises(ValidationError, match="1つ以上"):
        add_starters(user, [])
    assert not Event.objects.exists()


def test_知らないテンプレートが混ざっていたら_何も追加しない(user):
    with pytest.raises(ValidationError):
        add_starters(user, ["sheets", "no-such-template"])
    assert not Event.objects.exists()


def test_ほかの人のイベントは_追加済みかどうかに関係しない(user):
    other = new_user(email="b@example.com")
    add_starters(other, ["sheets"])

    assert [c.key for c in starter_choices(user) if c.added] == []
    assert [e.name for e in add_starters(user, ["sheets"])] == ["シーツ交換"]


def test_一覧では_追加済みのテンプレートが分かる(user):
    add_starters(user, ["sheets"])
    assert [c.key for c in starter_choices(user) if c.added] == ["sheets"]
    assert len(starter_choices(user)) == len(STARTERS)
