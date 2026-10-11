"""イベントとカテゴリの作成・編集・並べ替え（SPEC 3.1・3.4、決定 008・013）。"""

import unicodedata
import uuid
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.events.models import COLORS, Category, Event, StreakUnit
from apps.events.services import sortkeys
from apps.events.services.access import category_for, event_for
from apps.events.services.dates import now_utc
from apps.events.services.logs import When, record, refresh_event_cache
from apps.spaces.services import personal_space


def _clean_name(name: str, max_len: int, label: str) -> str:
    name = unicodedata.normalize("NFC", (name or "").strip())
    if not name:
        raise ValidationError(f"{label}を入力してください", code="required")
    if len(name) > max_len:
        raise ValidationError(f"{label}は{max_len}文字までです", code="too_long")
    return name


def _clean_emoji(emoji: str) -> str:
    emoji = (emoji or "").strip()
    if not emoji or len(emoji) > 16:
        raise ValidationError("アイコンを選んでください", code="emoji")
    return emoji


def _check(color: str, unit: str) -> None:
    if color not in COLORS:
        raise ValidationError("色を選んでください", code="color")
    if unit not in StreakUnit.values:
        raise ValidationError("連続記録の単位を選んでください", code="unit")


def _category_or_none(user, category_id) -> Category | None:
    if not category_id:
        return None
    try:
        return category_for(user, category_id)
    except Category.DoesNotExist:
        raise ValidationError("カテゴリが見つかりません", code="category") from None


def _neighbor_keys(qs, before_id, after_id) -> tuple[str | None, str | None]:
    """並べ替えの前後のキー。指定された ID が見つからなければエラーにする（黙って無視しない、レビュー 2）。"""

    def key_of(neighbor_id) -> str:
        key = qs.filter(id=neighbor_id).values_list("sort_key", flat=True).first()
        if key is None:
            raise ValidationError("並べ替えの位置が見つかりません", code="neighbor")
        return key

    lo = key_of(before_id) if before_id else None
    hi = key_of(after_id) if after_id else None
    if lo is not None and hi is None:
        hi = qs.filter(sort_key__gt=lo).order_by("sort_key").values_list("sort_key", flat=True).first()
    elif hi is not None and lo is None:
        lo = qs.filter(sort_key__lt=hi).order_by("-sort_key").values_list("sort_key", flat=True).first()
    if lo is not None and hi is not None and lo >= hi:
        raise ValidationError("並び順の指定が正しくありません", code="order")
    return lo, hi


def _key_between(lo: str | None, hi: str | None) -> str:
    """ソートキーを作る。DB に不正なキーが入っていた場合も 500 にせず、入力エラーとして扱う（レビュー2回目 #10）。"""
    try:
        return sortkeys.key_between(lo, hi)
    except ValueError:
        raise ValidationError("並び順を決められませんでした。もう一度お試しください", code="sort_key") from None


def _first_key(qs) -> str | None:
    return qs.order_by("sort_key").values_list("sort_key", flat=True).first()


@transaction.atomic
def create_event(
    user,
    *,
    name: str,
    emoji: str,
    color: str,
    streak_unit: str = StreakUnit.DAY,
    category_id=None,
    last_done: date | None = None,
    now: datetime | None = None,
) -> Event:
    """イベントを先頭に作る。last_done（前回やった日）があれば、時刻なしの記録を1件作る（SPEC 3.2.1）。"""
    space = personal_space(user)
    _check(color, streak_unit)
    event = Event.objects.create(
        space=space,
        name=_clean_name(name, 40, "名前"),
        emoji=_clean_emoji(emoji),
        color=color,
        streak_unit=streak_unit,
        category=_category_or_none(user, category_id),
        sort_key=_key_between(None, _first_key(Event.objects.filter(space=space))),
        created_by=user,
    )
    if last_done is not None:
        record(user, event.id, uuid.uuid7(), When(date=last_done), now=now or now_utc())
        event.refresh_from_db()
    return event


@transaction.atomic
def update_event(user, event_id, *, name: str, emoji: str, color: str, streak_unit: str, category_id=None) -> Event:
    event = event_for(user, event_id, lock=True)
    _check(color, streak_unit)
    unit_changed = event.streak_unit != streak_unit
    event.name = _clean_name(name, 40, "名前")
    event.emoji = _clean_emoji(emoji)
    event.color = color
    event.streak_unit = streak_unit
    event.category = _category_or_none(user, category_id)
    event.save()
    if unit_changed:
        refresh_event_cache(event)
    return event


@transaction.atomic
def set_archived(user, event_id, archived: bool, now: datetime | None = None) -> Event:
    event = event_for(user, event_id, lock=True)
    event.is_archived = archived
    event.archived_at = (now or now_utc()) if archived else None
    if not archived:
        # アーカイブから戻したイベントは先頭に置く
        event.sort_key = _key_between(None, _first_key(Event.objects.filter(space=event.space).exclude(id=event.id)))
    event.save()
    return event


@transaction.atomic
def delete_event(user, event_id) -> None:
    event_for(user, event_id).delete()  # 記録も CASCADE で消える


@transaction.atomic
def move_event(user, event_id, *, before_id=None, after_id=None) -> Event:
    """並べ替え。動かしたイベントを before と after の間に置き、そのイベントのキーだけを更新する。

    カテゴリのタブで並べ替えた場合も、画面上の前後のイベントを渡せば、
    そのカテゴリ内の順番だけが入れ替わり、他のイベントの位置は変わらない（決定 013）。
    """
    event = event_for(user, event_id, lock=True)
    qs = Event.objects.filter(space=event.space).exclude(id=event.id)
    event.sort_key = _key_between(*_neighbor_keys(qs, before_id, after_id))
    event.save(update_fields=["sort_key", "updated_at"])
    return event


# --- カテゴリ -----------------------------------------------------------------


@transaction.atomic
def create_category(user, name: str) -> Category:
    space = personal_space(user)
    name = _clean_name(name, 20, "カテゴリ名")
    if existing := Category.objects.filter(space=space, name=name).first():
        return existing
    last = Category.objects.filter(space=space).order_by("-sort_key").values_list("sort_key", flat=True).first()
    return Category.objects.create(space=space, name=name, sort_key=_key_between(last, None))


@transaction.atomic
def rename_category(user, category_id, name: str) -> Category:
    cat = category_for(user, category_id)
    name = _clean_name(name, 20, "カテゴリ名")
    if Category.objects.filter(space=cat.space, name=name).exclude(id=cat.id).exists():
        raise ValidationError("同じ名前のカテゴリがあります", code="duplicate")
    cat.name = name
    cat.save(update_fields=["name", "updated_at"])
    return cat


@transaction.atomic
def delete_category(user, category_id) -> None:
    """カテゴリを消しても、イベントと記録は残る（カテゴリは「なし」になる）。"""
    category_for(user, category_id).delete()


@transaction.atomic
def move_category(user, category_id, *, before_id=None, after_id=None) -> Category:
    cat = category_for(user, category_id)
    qs = Category.objects.filter(space=cat.space).exclude(id=cat.id)
    cat.sort_key = _key_between(*_neighbor_keys(qs, before_id, after_id))
    cat.save(update_fields=["sort_key", "updated_at"])
    return cat


@transaction.atomic
def shift_category(user, category_id, direction: int) -> Category:
    """カテゴリを1つ上（-1）または下（+1）へ動かす。端なら何もしない。"""
    cat = category_for(user, category_id)
    siblings = list(Category.objects.filter(space=cat.space).order_by("sort_key"))
    i = next(i for i, c in enumerate(siblings) if c.id == cat.id)
    j = i + direction
    if not 0 <= j < len(siblings):
        return cat
    if direction < 0:
        return move_category(user, cat.id, after_id=siblings[j].id)
    return move_category(user, cat.id, before_id=siblings[j].id)
