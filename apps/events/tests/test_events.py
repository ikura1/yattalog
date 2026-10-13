"""イベント・カテゴリの操作と統計。"""

import uuid
from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError

from apps.core.testing import NOW, TODAY
from apps.events.models import Category, Event
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


def test_新しいイベントは先頭に入る(user):
    make(user, "A")
    make(user, "B")
    assert names(user) == ["B", "A"]


def test_カテゴリ内で並べ替えても他のイベントの位置は変わらない(user):
    house = ev_svc.create_category(user, "家事")
    a = make(user, "a", house)
    make(user, "x")
    make(user, "b", house)
    make(user, "y")
    c = make(user, "c", house)
    assert names(user) == ["c", "y", "b", "x", "a"]
    ev_svc.move_event(user, a.id, after_id=c.id)  # 家事のタブで a を先頭へ
    assert names(user, house) == ["a", "c", "b"]
    assert [n for n in names(user) if n in "xy"] == ["y", "x"]


@pytest.mark.parametrize("which", ["他人のイベント", "存在しないID", "自分自身"])
def test_並べ替えの前後に見つからないIDを渡すとエラーになる(user, other_user, which):
    a = make(user, "a")
    b = make(user, "b")
    neighbor = {
        "他人のイベント": lambda: make(other_user, "x").id,
        "存在しないID": uuid.uuid4,
        "自分自身": lambda: b.id,
    }[which]()
    with pytest.raises(ValidationError):
        ev_svc.move_event(user, b.id, before_id=neighbor)
    keys = list(Event.objects.filter(id__in=[a.id, b.id]).values_list("sort_key", flat=True))
    assert len(set(keys)) == 2  # キーが重複していない（レビュー 2）


def test_カテゴリを消してもイベントは残りカテゴリなしになる(user):
    house = ev_svc.create_category(user, "家事")
    e = make(user, "a", house)
    ev_svc.delete_category(user, house.id)
    e.refresh_from_db()
    assert e.category is None


def test_他人のカテゴリには入れられない(user, other_user):
    theirs = ev_svc.create_category(other_user, "趣味")
    with pytest.raises(ValidationError):
        make(user, "a", theirs)


def test_他人のカテゴリは操作できない(user, other_user):
    theirs = ev_svc.create_category(other_user, "趣味")
    with pytest.raises(Category.DoesNotExist):
        ev_svc.shift_category(user, theirs.id, -1)


def test_カテゴリを上下に動かせて端では何もしない(user):
    a, b, c = (ev_svc.create_category(user, n) for n in "abc")
    ev_svc.shift_category(user, c.id, -1)
    ev_svc.shift_category(user, a.id, -1)
    assert list(Category.objects.order_by("sort_key").values_list("name", flat=True)) == ["a", "c", "b"]


def test_名前は必須(user):
    with pytest.raises(ValidationError):
        ev_svc.create_event(user, name="  ", emoji="⭐", color="sky")


@pytest.mark.parametrize("emoji", ["🥟", "❤️", "👍🏽", "👨‍👩‍👧", "🇯🇵", "1️⃣", "🏴󠁧󠁢󠁥󠁮󠁧󠁿"])
def test_アイコンは絵文字なら何でも使える(user, emoji):
    assert ev_svc.create_event(user, name="ぎょうざ", emoji=f" {emoji} ", color="sky").emoji == emoji


@pytest.mark.parametrize("not_one_emoji", ["", "a", "あ", "1", ":)", "🪴🪴", "🪴a", "🇯", "\u200d"])
def test_アイコンは絵文字1つでなければ弾く(user, not_one_emoji):
    with pytest.raises(ValidationError, match="絵文字を1つ"):
        ev_svc.create_event(user, name="水やり", emoji=not_one_emoji, color="sky")


def test_編集でも絵文字でないアイコンは弾く(user):
    e = make(user, "水やり")
    with pytest.raises(ValidationError, match="絵文字を1つ"):
        ev_svc.update_event(user, e.id, name="水やり", emoji="abc", color="sky", streak_unit="day")


def test_アーカイブから戻したイベントは先頭に入る(user):
    a = make(user, "a")
    make(user, "b")
    ev_svc.set_archived(user, a.id, True)
    assert names(user) == ["b"]
    ev_svc.set_archived(user, a.id, False)
    assert names(user) == ["a", "b"]


@pytest.fixture
def futon(user):
    e = make(user, "布団")
    for d in [date(2026, 4, 1), date(2026, 4, 8), date(2026, 4, 15), date(2026, 5, 1), date(2026, 9, 1)]:
        log_svc.record(user, e.id, uuid.uuid7(), When(date=d))
    e.refresh_from_db()
    return e


def test_記録回数と今年の回数とペース(futon):
    s = stats.event_stats(futon, TODAY)
    assert (s.total, s.this_year, s.pace) == (5, 5, "だいたい5週間ごと")


def test_よくやる時期は最大の7割以上の月(futon):
    season = stats.season(futon, 2026)
    assert (season.counts[3], season.headline) == (3, "よくやるのは 4月")


def test_全期間の年の一覧(futon):
    assert stats.season(futon, None).years == [2026]


def test_記録がある日が1日だけならペースは出さない(user):
    e = make(user, "a")
    log_svc.record(user, e.id, uuid.uuid7(), When(date=date(2026, 1, 1)))
    e.refresh_from_db()
    assert stats.event_stats(e, TODAY).pace is None


def test_壊れたソートキーが入っていても並べ替えは入力エラーになる(user):
    # DB を手で直したときなどに、不正なキーで 500 にならないようにする（レビュー2回目 #10）
    a = make(user, "a")
    b = make(user, "b")
    Event.objects.filter(id=a.id).update(sort_key="!!")
    with pytest.raises(ValidationError):
        ev_svc.move_event(user, b.id, after_id=a.id)


# --- カテゴリの絵文字（任意、決定 036） ---


def test_カテゴリは絵文字つきでも_なしでも作れる(user):
    assert ev_svc.create_category(user, "家事", emoji=" 🧹 ").emoji == "🧹"
    assert ev_svc.create_category(user, "趣味").emoji == ""


@pytest.mark.parametrize("not_one_emoji", ["a", "あ", "🧹🧺", "🧹a"])
def test_カテゴリの絵文字は_入れるなら絵文字1つ(user, not_one_emoji):
    with pytest.raises(ValidationError, match="絵文字を1つ"):
        ev_svc.create_category(user, "家事", emoji=not_one_emoji)
    assert not Category.objects.exists()


def test_カテゴリの絵文字は_あとから付けたり外したりできる(user):
    house = ev_svc.create_category(user, "家事")

    assert ev_svc.rename_category(user, house.id, "家事", emoji="🧹").emoji == "🧹"
    assert ev_svc.rename_category(user, house.id, "そうじ").emoji == "🧹"  # 絵文字を渡さなければそのまま
    assert ev_svc.rename_category(user, house.id, "そうじ", emoji="").emoji == ""


def test_カテゴリの絵文字が正しくなければ_名前も変わらない(user):
    house = ev_svc.create_category(user, "家事", emoji="🧹")
    with pytest.raises(ValidationError, match="絵文字を1つ"):
        ev_svc.rename_category(user, house.id, "そうじ", emoji="abc")
    house.refresh_from_db()
    assert (house.name, house.emoji) == ("家事", "🧹")


# --- 一覧（画面からは、ここを通して読む。決定 027） ---


def test_ホームに出すイベントは_自分のもので_アーカイブしていないものを_並び順で(user, other_user):
    make(user, "a")
    b = make(user, "b")
    make(other_user, "よその人の")
    ev_svc.set_archived(user, b.id, True)
    make(user, "c")

    assert [e.name for e in ev_svc.list_events(user)] == ["c", "a"]


def test_アーカイブしたイベントは_新しくアーカイブした順で(user, other_user):
    a, b = make(user, "a"), make(user, "b")
    ev_svc.set_archived(other_user, make(other_user, "よその人の").id, True)
    ev_svc.set_archived(user, a.id, True, now=NOW)
    ev_svc.set_archived(user, b.id, True, now=NOW + timedelta(minutes=1))

    assert [e.name for e in ev_svc.list_archived(user)] == ["b", "a"]


def test_カテゴリの一覧は_自分のものを_タブの並び順で(user, other_user):
    ev_svc.create_category(user, "家事")
    ev_svc.create_category(other_user, "よその人の")
    ev_svc.create_category(user, "趣味")

    assert [c.name for c in ev_svc.list_categories(user)] == ["家事", "趣味"]
