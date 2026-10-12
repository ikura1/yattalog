"""はじめて使うときのテンプレート（SPEC 3.6、決定 009・042）。

テンプレートはコードの中の固定データ。選んだものを、ふつうのイベントとしてまとめて作る。
"""

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.events.models import Event
from apps.events.services.events import create_category, create_event
from apps.spaces.services import personal_space


@dataclass(frozen=True)
class Starter:
    key: str
    name: str
    emoji: str
    color: str
    streak_unit: str
    category: str


# 並び順が、そのまま画面とホームでの順番になる
STARTERS = [
    Starter("watering", "植物の水やり", "🪴", "leaf", "day", "家事"),
    Starter("sheets", "シーツ交換", "🛏️", "sky", "week", "家事"),
    Starter("futon", "布団を干す", "☀️", "sun", "week", "家事"),
    Starter("ac-filter", "エアコンのフィルター掃除", "🌀", "teal", "month", "家事"),
    Starter("fan", "換気扇の掃除", "🧽", "tangerine", "none", "家事"),
    Starter("car-wash", "洗車", "🚗", "sky", "month", "家事"),
    Starter("haircut", "散髪", "✂️", "grape", "month", "身の回り"),
    Starter("dentist", "歯医者", "🦷", "pink", "none", "身の回り"),
    Starter("family", "実家に連絡", "📞", "tangerine", "month", "身の回り"),
    Starter("gym", "ジム", "🏋️", "tomato", "week", "趣味"),
]
BY_KEY = {s.key: s for s in STARTERS}


@dataclass(frozen=True)
class Choice:
    """画面に出す1行分。同じ名前のイベントをもう持っていれば added。"""

    starter: Starter
    added: bool

    @property
    def key(self) -> str:
        return self.starter.key


def _own_names(user) -> set[str]:
    return set(Event.objects.filter(space=personal_space(user)).values_list("name", flat=True))


def starter_choices(user) -> list[Choice]:
    names = _own_names(user)
    return [Choice(s, s.name in names) for s in STARTERS]


@transaction.atomic
def add_starters(user, keys: list[str]) -> list[Event]:
    """選んだテンプレートをイベントとして作る。同じ名前のイベントがすでにあるものは飛ばす。"""
    if not keys:
        raise ValidationError("追加するものを1つ以上選んでください", code="required")
    if unknown := [k for k in keys if k not in BY_KEY]:
        raise ValidationError(f"知らないテンプレートです：{unknown[0]}", code="unknown")
    names = _own_names(user)
    chosen = [s for s in STARTERS if s.key in set(keys) and s.name not in names]
    # カテゴリは一覧の順に作る（タブの並びになる）
    categories = {}
    for s in chosen:
        if s.category not in categories:
            categories[s.category] = create_category(user, s.category)
    # 新しいイベントは先頭に入るので、後ろから作ると、ホームでも一覧と同じ順に並ぶ
    events = [
        create_event(
            user,
            name=s.name,
            emoji=s.emoji,
            color=s.color,
            streak_unit=s.streak_unit,
            category_id=categories[s.category].id,
        )
        for s in reversed(chosen)
    ]
    return list(reversed(events))
