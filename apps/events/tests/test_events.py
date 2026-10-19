"""イベント・カテゴリの操作と統計。"""

import uuid
from datetime import date, time, timedelta

import pytest
from django.core.exceptions import ValidationError

from apps.core.testing import NOW, TODAY, new_user
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


# --- 最高連続（決定 059） ---


def logs_on(user, event, *days):
    for d in days:
        log_svc.record(user, event.id, uuid.uuid7(), When(date=d))
    event.refresh_from_db()
    return event


def test_最高連続は_これまでで一番長く続いた回数_途切れていても残る(user):
    # 毎週：9月の3週連続のあと途切れ、10月に2週連続（いまの連続より、前の記録のほうが長い）
    e = ev_svc.create_event(user, name="ジョギング", emoji="🏃", color="leaf", streak_unit="week")
    logs_on(
        user,
        e,
        date(2026, 8, 31),
        date(2026, 9, 7),
        date(2026, 9, 9),
        date(2026, 9, 14),
        date(2026, 10, 3),
        date(2026, 10, 5),
    )
    s = stats.event_stats(e, TODAY)
    assert (s.best_streak, s.best_streak_text) == (3, "3週連続")


def test_最高連続は_連続の単位がないイベントでは出さない(user):
    e = ev_svc.create_event(user, name="歯医者", emoji="🦷", color="pink", streak_unit="none")
    logs_on(user, e, date(2026, 10, 9), date(2026, 10, 10))
    s = stats.event_stats(e, TODAY)
    assert (s.best_streak, s.best_streak_text) == (0, "")


def test_最高連続は_2回に届かなければ出さない(user):
    e = ev_svc.create_event(user, name="ヨガ", emoji="🧘", color="teal", streak_unit="day")
    logs_on(user, e, date(2026, 10, 1), date(2026, 10, 5))
    assert stats.event_stats(e, TODAY).best_streak_text == ""


def test_最高連続は_毎日と毎月でも数える(user):
    daily = ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf", streak_unit="day")
    monthly = ev_svc.create_event(user, name="散髪", emoji="✂️", color="pink", streak_unit="month")
    logs_on(user, daily, date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3), date(2026, 10, 9))
    logs_on(user, monthly, date(2025, 12, 20), date(2026, 1, 5), date(2026, 3, 1))
    assert stats.event_stats(daily, TODAY).best_streak_text == "3日連続"
    assert stats.event_stats(monthly, TODAY).best_streak_text == "2か月連続"


# --- はじめての記録から（決定 060） ---


def test_詳細の統計に_はじめて記録した日を持つ(user):
    e = ev_svc.create_event(user, name="ヨガ", emoji="🧘", color="teal")
    logs_on(user, e, date(2025, 8, 3), date(2026, 10, 1))
    assert stats.event_stats(e, TODAY).first == date(2025, 8, 3)


@pytest.mark.parametrize(
    ("first", "expected"),
    [
        (date(2026, 10, 10), "今日"),
        (date(2026, 10, 1), "9日前"),
        (date(2026, 9, 11), "29日前"),
        (date(2026, 9, 10), "1か月前"),
        (date(2025, 11, 11), "10か月前"),
        (date(2025, 10, 10), "1年前"),
        (date(2025, 8, 3), "1年2か月前"),
        (date(2023, 10, 11), "2年11か月前"),
    ],
)
def test_はじめての記録が_どれくらい前かを言う(first, expected):
    assert stats.since_text(first, TODAY) == expected


# --- そのイベントのくせ：よくやる曜日・時間帯・日にち（決定 060） ---


def at(user, event, day, hh, mm=0):
    log_svc.record(user, event.id, uuid.uuid7(), When(date=day, time=time(hh, mm)))


def test_よくやる曜日は_そのイベントのこれまでの記録を_週の始まりから数える(user):
    e = ev_svc.create_event(user, name="ジョギング", emoji="🏃", color="leaf")
    other = ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf")
    logs_on(user, e, date(2025, 3, 1), date(2026, 9, 26), date(2026, 10, 3), date(2026, 10, 7))  # 土×3、水
    logs_on(user, other, date(2026, 10, 5))

    t = stats.weekday_tendency(e)

    assert (t.counts, t.headline) == ([0, 0, 1, 0, 0, 3, 0], "よくやるのは 土曜")  # 月曜から（決定 066）


def test_よくやる曜日は_記録が少ないうちは_わかるようになると伝える(user):
    e = ev_svc.create_event(user, name="ヨガ", emoji="🧘", color="teal")
    logs_on(user, e, date(2026, 10, 3))
    assert stats.weekday_tendency(e).headline == "記録が増えると、よくやる曜日がわかります"


def test_時間帯は_朝昼夕方夜の4つに分けて数える_時刻なしの記録は数えない(user):
    e = ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf")
    d = TODAY - timedelta(1)
    at(user, e, d, 4)  # 朝：4:00〜10:59
    at(user, e, d, 10, 59)
    at(user, e, d, 11)  # 昼：11:00〜15:59
    at(user, e, d, 18, 59)  # 夕方：16:00〜18:59
    at(user, e, d, 3, 59)  # 夜：19:00〜3:59
    logs_on(user, e, d)  # 時刻なし

    t = stats.time_tendency(e)

    assert (t.counts, t.headline) == ([2, 1, 1, 1], "よくやるのは 朝")


def test_時間帯は_記録したときのタイムゾーンで数える(user):
    user.timezone = "America/New_York"
    user.save()
    e = ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf")
    at(user, e, TODAY - timedelta(1), 7)  # ニューヨークの朝7時（日本では夜）
    assert stats.time_tendency(e).counts == [1, 0, 0, 0]


def test_時刻つきの記録が少ないうちは_時間帯はわかるようになると伝える(user):
    e = ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf")
    logs_on(user, e, date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3))
    assert stats.time_tendency(e).headline == "時刻つきの記録が増えると、よくやる時間帯がわかります"


def test_よくやる日にちは_1日から31日で数え_上旬中旬下旬で見出しにする(user):
    e = ev_svc.create_event(user, name="家計簿", emoji="📒", color="sun")
    logs_on(user, e, date(2026, 7, 1), date(2026, 8, 1), date(2026, 9, 2), date(2026, 10, 5), date(2026, 8, 31))

    days = stats.month_days(e)

    assert days.counts[0] == 2 and days.counts[1] == 1 and days.counts[4] == 1 and days.counts[30] == 1
    assert len(days.counts) == 31
    assert days.tendency.headline == "よくやるのは 上旬"


def test_よくやる日にちの濃さは_一番多い日を4として段階に分ける(user):
    e = ev_svc.create_event(user, name="家計簿", emoji="📒", color="sun")
    logs_on(user, e, date(2026, 7, 1), date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1), date(2026, 10, 2))
    levels = stats.month_days(e).levels
    assert (levels[0], levels[1], levels[2]) == (4, 1, 0)


# --- いちばんよくやった月（決定 062） ---


def test_いちばんよくやった月を出す_同じなら新しいほう(user):
    e = ev_svc.create_event(user, name="布団を干す", emoji="☀️", color="sun")
    logs_on(user, e, date(2025, 4, 1), date(2025, 4, 9), date(2026, 4, 2), date(2026, 4, 20), date(2026, 5, 1))
    assert stats.event_stats(e, TODAY).best_month_text == "いちばんよくやったのは 2026年4月（2回）"


def test_いちばんよくやった月は_2回に届かなければ出さない(user):
    e = ev_svc.create_event(user, name="散髪", emoji="✂️", color="pink")
    logs_on(user, e, date(2026, 6, 1), date(2026, 8, 1))
    assert stats.event_stats(e, TODAY).best_month_text == ""


# --- カテゴリの一覧と、中のイベント（カテゴリの編集画面） ---


def test_カテゴリの一覧には_中のイベントの数と_先頭の絵文字を5つまで添える(user):
    house = ev_svc.create_category(user, "家のこと")
    ev_svc.create_category(user, "からだ")
    for i, e in enumerate(["🛏️", "🚽", "🛁", "🧺", "🧊", "🌀"]):
        ev_svc.create_event(user, name=f"e{i}", emoji=e, color="sky", category_id=house.id)
    archived = ev_svc.create_event(user, name="昔の", emoji="📦", color="sky", category_id=house.id)
    ev_svc.set_archived(user, archived.id, True)

    rows = ev_svc.category_rows(user)

    assert [(r.category.name, r.count) for r in rows] == [("家のこと", 6), ("からだ", 0)]
    assert len(rows[0].emojis) == 5 and "📦" not in rows[0].emojis


def test_カテゴリに入っているイベントを_ホームの並び順で返す_ほかの人のカテゴリは見えない(user):
    house = ev_svc.create_category(user, "家のこと")
    a = ev_svc.create_event(user, name="a", emoji="⭐", color="sky", category_id=house.id)
    b = ev_svc.create_event(user, name="b", emoji="⭐", color="sky", category_id=house.id)
    ev_svc.create_event(user, name="c", emoji="⭐", color="sky")
    assert ev_svc.events_in_category(user, house.id) == [b, a]
    other = new_user(email="b@example.com")
    with pytest.raises(Category.DoesNotExist):
        ev_svc.events_in_category(other, house.id)
