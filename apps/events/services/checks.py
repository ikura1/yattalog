"""チェックする記録（決定 076）。イベントに項目を決めておき、記録のたびに、やったものを選ぶ。

記録には、選んだ項目の名前そのものを残す。後から項目を変えても、前の記録は前の名前のまま。
"""

import unicodedata
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from django.core.exceptions import ValidationError

from apps.events.models import Event, NumberKind

ITEMS_MAX = 8  # 1つのイベントに持てる項目の数（シートが1画面に収まる数）
ITEM_NAME_MAX = 12


def clean_items(kind: str, items: Iterable[str]) -> list[str]:
    """項目の名前を整える。空の行は落とし、同じ名前は1つにする。チェックするイベントには、1つは要る。"""
    names = list(dict.fromkeys(n for n in (unicodedata.normalize("NFC", (i or "").strip()) for i in items) if n))
    if any(len(n) > ITEM_NAME_MAX for n in names):
        raise ValidationError(f"項目は{ITEM_NAME_MAX}文字までです", code="check_item_too_long")
    if len(names) > ITEMS_MAX:
        raise ValidationError(f"項目は{ITEMS_MAX}個までです", code="check_items_too_many")
    if kind == NumberKind.CHECK and not names:
        raise ValidationError("チェックする項目を1つ以上入れてください", code="check_items_required")
    return names


def clean_checks(event: Event, posted: Iterable[str], keep: Iterable[str] = ()) -> list[str]:
    """選ばれた項目を、項目の順にそろえる。keep（その記録に残っている前の名前）は、後ろに並べる。

    項目にないものは断る（項目を変えたあとの古いシートから。黙って捨てると、選んだものが消える）。
    """
    chosen = set(posted)
    allowed = [*event.check_items, *(k for k in keep if k not in event.check_items)]
    if chosen - set(allowed):
        raise ValidationError("項目が変わっています。シートを開き直してください", code="check_unknown")
    return [name for name in allowed if name in chosen]


def last_checks(event: Event) -> list[str]:
    """前回のチェック（いちばん新しい記録のもの）。記録するシートで、はじめから印を入れておく。"""
    last = event.logs.values_list("checks", flat=True).first() or []
    return [name for name in event.check_items if name in last]


@dataclass(frozen=True)
class CheckStats:
    rows: list[tuple[str, int]]  # （項目, 回数）。いまの項目の順で、いまはない項目は後ろ
    count: int  # チェックの付いた記録の数
    top: int  # いちばん多い項目の回数


def check_stats(event: Event) -> CheckStats | None:
    """どれを何回やったか。チェックしないイベントなら None。"""
    if not event.is_check:
        return None
    marked = [c for c in event.logs.values_list("checks", flat=True) if c]
    counts = Counter(name for c in marked for name in c)
    past = [name for name in counts if name not in event.check_items]
    rows = [(name, counts[name]) for name in [*event.check_items, *past]]
    return CheckStats(rows, len(marked), max((n for _, n in rows), default=0))
