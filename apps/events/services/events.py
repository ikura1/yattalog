"""イベントとカテゴリの作成・編集・並べ替え（SPEC 3.1・3.4、決定 008・013）。"""

import unicodedata

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.events.models import COLORS, Category, Event, StreakUnit
from apps.events.services import sortkeys
from apps.events.services.logs import When, record
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


def category_for(user, category_id) -> Category | None:
    if not category_id:
        return None
    try:
        return Category.objects.get(id=category_id, space__members__user=user)
    except Category.DoesNotExist, ValueError, ValidationError:
        raise ValidationError("カテゴリが見つかりません", code="category") from None


@transaction.atomic
def create_event(
    user,
    *,
    name: str,
    emoji: str,
    color: str,
    streak_unit: str = StreakUnit.DAY,
    category_id=None,
    last_done=None,
    log_id=None,
) -> Event:
    """イベントを先頭に作る。last_done（前回やった日）があれば、時刻なしの記録を1件作る（SPEC 3.2.1）。"""
    space = personal_space(user)
    _check(color, streak_unit)
    first = Event.objects.filter(space=space).order_by("sort_key").values_list("sort_key", flat=True).first()
    event = Event.objects.create(
        space=space,
        name=_clean_name(name, 40, "名前"),
        emoji=_clean_emoji(emoji),
        color=color,
        streak_unit=streak_unit,
        category=category_for(user, category_id),
        sort_key=sortkeys.key_first(first),
        created_by=user,
    )
    if last_done is not None:
        import uuid

        record(user, event.id, log_id or uuid.uuid7(), When(date=last_done))
        event.refresh_from_db()
    return event


@transaction.atomic
def update_event(user, event_id, *, name: str, emoji: str, color: str, streak_unit: str, category_id=None) -> Event:
    from apps.events.services.logs import get_event_for, refresh_event_cache

    event = get_event_for(user, event_id)
    _check(color, streak_unit)
    unit_changed = event.streak_unit != streak_unit
    event.name = _clean_name(name, 40, "名前")
    event.emoji = _clean_emoji(emoji)
    event.color = color
    event.streak_unit = streak_unit
    event.category = category_for(user, category_id)
    event.save()
    if unit_changed:
        refresh_event_cache(event)
    return event


@transaction.atomic
def set_archived(user, event_id, archived: bool) -> Event:
    from apps.events.services.logs import get_event_for

    event = get_event_for(user, event_id)
    event.is_archived = archived
    event.archived_at = timezone.now() if archived else None
    if not archived:
        # アーカイブから戻したイベントは先頭に置く
        first = (
            Event.objects.filter(space=event.space, is_archived=False)
            .order_by("sort_key")
            .values_list("sort_key", flat=True)
            .first()
        )
        event.sort_key = sortkeys.key_first(first)
    event.save()
    return event


@transaction.atomic
def delete_event(user, event_id) -> None:
    from apps.events.services.logs import get_event_for

    get_event_for(user, event_id).delete()  # 記録も CASCADE で消える


@transaction.atomic
def move_event(user, event_id, *, before_id=None, after_id=None) -> Event:
    """並べ替え。動かしたイベントを before と after の間に置き、そのイベントのキーだけを更新する。

    カテゴリのタブで並べ替えた場合も、画面上の前後のイベントを渡せば、
    そのカテゴリ内の順番だけが入れ替わり、他のイベントの位置は変わらない（決定 013）。
    """
    from apps.events.services.logs import get_event_for

    event = get_event_for(user, event_id)
    qs = Event.objects.filter(space=event.space).exclude(id=event.id)
    lo = qs.filter(id=before_id).values_list("sort_key", flat=True).first() if before_id else None
    hi = qs.filter(id=after_id).values_list("sort_key", flat=True).first() if after_id else None
    if lo is not None and hi is None:
        # before の直後に入れる：before と、全体での次のキーの間
        hi = qs.filter(sort_key__gt=lo).order_by("sort_key").values_list("sort_key", flat=True).first()
    elif hi is not None and lo is None:
        lo = qs.filter(sort_key__lt=hi).order_by("-sort_key").values_list("sort_key", flat=True).first()
    if lo is not None and hi is not None and lo >= hi:
        raise ValidationError("並び順の指定が正しくありません", code="order")
    event.sort_key = sortkeys.key_between(lo, hi)
    event.save(update_fields=["sort_key", "updated_at"])
    return event


# --- カテゴリ -----------------------------------------------------------------


@transaction.atomic
def create_category(user, name: str) -> Category:
    space = personal_space(user)
    name = _clean_name(name, 20, "カテゴリ名")
    existing = Category.objects.filter(space=space, name=name).first()
    if existing:
        return existing
    last = Category.objects.filter(space=space).order_by("-sort_key").values_list("sort_key", flat=True).first()
    return Category.objects.create(space=space, name=name, sort_key=sortkeys.key_last(last))


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
    lo = qs.filter(id=before_id).values_list("sort_key", flat=True).first() if before_id else None
    hi = qs.filter(id=after_id).values_list("sort_key", flat=True).first() if after_id else None
    if lo is not None and hi is None:
        hi = qs.filter(sort_key__gt=lo).order_by("sort_key").values_list("sort_key", flat=True).first()
    elif hi is not None and lo is None:
        lo = qs.filter(sort_key__lt=hi).order_by("-sort_key").values_list("sort_key", flat=True).first()
    cat.sort_key = sortkeys.key_between(lo, hi)
    cat.save(update_fields=["sort_key", "updated_at"])
    return cat
