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


# 対象は独身・一人暮らしの20〜30代（決定 065）。組（＝作るカテゴリ）と、その説明。並び順が、画面とタブの順番になる
GROUPS = {
    "家のこと": "一人暮らしだと、誰も代わりに覚えていてくれないもの",
    "身だしなみ": "間隔が空いて、忘れがちなもの",
    "からだ": "",
    "人づきあい": "",
    "楽しみ": "",
}

# 並び順が、そのまま画面とホームでの順番になる
STARTERS = [
    Starter("sheets", "シーツ交換", "🛏️", "sky", "week", "家のこと"),
    Starter("futon", "布団を干す", "☀️", "sun", "week", "家のこと"),
    Starter("toilet", "トイレ掃除", "🚽", "teal", "week", "家のこと"),
    Starter("bath", "お風呂の掃除", "🛁", "sky", "week", "家のこと"),
    Starter("drain", "排水口の掃除", "🕳️", "grape", "month", "家のこと"),
    Starter("washer", "洗濯槽の掃除", "🧺", "teal", "month", "家のこと"),
    Starter("fridge", "冷蔵庫の整理", "🧊", "sky", "month", "家のこと"),
    Starter("ac-filter", "エアコンのフィルター掃除", "🌀", "teal", "month", "家のこと"),
    Starter("water-filter", "浄水器のカートリッジ交換", "🚰", "sky", "none", "家のこと"),
    Starter("disaster", "防災グッズの見直し", "🧯", "tomato", "none", "家のこと"),
    Starter("watering", "植物の水やり", "🪴", "leaf", "day", "家のこと"),
    Starter("supplies", "日用品の買い足し", "🧻", "tangerine", "none", "家のこと"),
    Starter("haircut", "美容院", "✂️", "grape", "month", "身だしなみ"),
    Starter("nail", "ネイル", "💅", "pink", "month", "身だしなみ"),
    Starter("brows", "眉・ムダ毛の手入れ", "🪒", "pink", "week", "身だしなみ"),
    Starter("toothbrush", "歯ブラシの交換", "🪥", "teal", "month", "身だしなみ"),
    Starter("contacts", "コンタクトの交換", "👓", "sky", "month", "身だしなみ"),
    Starter("shoes", "靴を洗う", "👟", "tangerine", "none", "身だしなみ"),
    Starter("dentist", "歯医者", "🦷", "pink", "none", "からだ"),
    Starter("gym", "ジム", "🏋️", "tomato", "week", "からだ"),
    Starter("running", "ランニング", "🏃", "leaf", "week", "からだ"),
    Starter("checkup", "健康診断", "🩺", "teal", "none", "からだ"),
    Starter("family", "実家に連絡", "📞", "tangerine", "month", "人づきあい"),
    Starter("friends", "友達とごはん", "🍻", "sun", "none", "人づきあい"),
    Starter("gift", "プレゼントを贈る", "🎁", "pink", "none", "人づきあい"),
    Starter("cinema", "映画館", "🎬", "grape", "none", "楽しみ"),
    Starter("travel", "旅行", "✈️", "sky", "none", "楽しみ"),
    Starter("reading", "本を読む", "📚", "tangerine", "week", "楽しみ"),
    Starter("oshi", "推し活", "🎤", "pink", "none", "楽しみ"),
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


@dataclass(frozen=True)
class Group:
    name: str
    note: str
    choices: list[Choice]


def starter_groups(user) -> list[Group]:
    """画面に出す一覧を、組ごとにまとめたもの。"""
    choices = starter_choices(user)
    return [Group(name, note, [c for c in choices if c.starter.category == name]) for name, note in GROUPS.items()]


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
