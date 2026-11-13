"""記録に付ける数字（決定 074）。受け取り方・出し方と、詳細に出す統計（合計・推移）。

数字はイベントごとに1つ。単位は自由で、足して見るか（距離・金額）、移り変わりを見るか（体重・体温）を
イベントごとに選ぶ。数字を記録するイベントでも、空のまま記録できる（空の記録は、統計に入れない）。
"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db.models import Count, Sum
from django.db.models.functions import ExtractMonth, ExtractYear

from apps.events.models import Event, Log, NumberKind

UNIT_MAX = 8
TREND_POINTS = 30  # 推移は、新しいほうからこの件数を見る（古い数字に、平均や最小・最大を引きずらせない）
SUM_MONTHS = 12  # 合計の棒は、今月までのこの月数
QUICK_MAX = 4  # よく使う数字のボタンの数（決定 075）
QUICK_RECENT = 50  # よく使う数字は、新しいほうからこの件数で数える（昔の習慣を引きずらせない）
QUICK_MIN_COUNT = 2  # この回数から「よく使う」とみなす
# 整数は9桁、小数は3桁まで（Log.value の桁数）。指数表記や符号は受け取らない
_NUMBER = re.compile(r"[0-9]{1,9}(?:\.[0-9]{0,3})?")
_ZERO = Decimal(0)


def clean_value(raw) -> Decimal | None:
    """入力された数字を Decimal にする。空なら None。全角の数字と、桁区切りのカンマも受け取る。"""
    text = unicodedata.normalize("NFKC", "" if raw is None else str(raw)).strip().replace(",", "")
    if not text:
        return None
    if not _NUMBER.fullmatch(text):
        raise ValidationError("数字は 0〜999,999,999 の範囲で入れてください（小数は3桁まで。例：5.2）", code="value")
    return Decimal(text)


def clean_unit(kind: str, unit: str) -> str:
    """数字の見せ方を確かめ、単位を整える。数字を記録しないなら、単位は持たない。"""
    if kind not in NumberKind.values:
        raise ValidationError("数字の記録のしかたを選んでください", code="number_kind")
    if kind == NumberKind.NONE:
        return ""
    unit = unicodedata.normalize("NFC", (unit or "").strip())
    if len(unit) > UNIT_MAX:
        raise ValidationError(f"単位は{UNIT_MAX}文字までです", code="number_unit")
    return unit


def plain_value(value: Decimal | None) -> str:
    """入力欄に入れる形（区切りなし、余分な 0 なし）。"""
    return "" if value is None else format(value.normalize(), "f")


def format_value(value: Decimal) -> str:
    """画面に出す形。「62.5」「1,200」。"""
    return format(value.normalize(), ",f")


def signed(diff: Decimal) -> str:
    """前回との差。「+1.25」「−0.6」「±0」。"""
    if diff == 0:
        return "±0"
    return ("+" if diff > 0 else "−") + format_value(abs(diff))


def _valued(event: Event):
    return Log.objects.filter(event=event, value__isnull=False)


def last_value(event: Event) -> Decimal | None:
    """前回の数字（数字の付いた、いちばん新しい記録のもの）。記録するシートに、はじめから入れておく。"""
    return _valued(event).values_list("value", flat=True).first()


def frequent_values(event: Event) -> list[Decimal]:
    """よく使う数字（決定 075）。回数の多い順で、同じ回数なら新しく使ったほうが先。"""
    recent = list(_valued(event).values_list("value", flat=True)[:QUICK_RECENT])  # 新しい順
    counts = Counter(recent)
    # sorted は順を保つので、同じ回数なら recent に先に出たほう（新しいほう）が前に残る
    ranked = sorted(dict.fromkeys(recent), key=lambda v: -counts[v])
    return [v for v in ranked if counts[v] >= QUICK_MIN_COUNT][:QUICK_MAX]


@dataclass(frozen=True)
class NumberSum:
    """合計で見る数字（距離・金額など）。"""

    unit: str
    month: Decimal  # 今月
    year: Decimal  # 今年
    total: Decimal  # これまで
    count: int  # 数字の付いた記録の数
    months: list[tuple[int, int, Decimal]]  # 今月までの12か月（年, 月, 合計）。古い順
    kind: str = NumberKind.SUM


@dataclass(frozen=True)
class NumberTrend:
    """推移で見る数字（体重・体温など）。新しいほうから TREND_POINTS 件で見る。"""

    unit: str
    latest: Decimal | None
    diff: Decimal | None  # 前回との差（数字が2つ以上あるとき）
    average: Decimal | None
    lowest: Decimal | None
    highest: Decimal | None
    count: int  # 見ている件数
    points: list[tuple[date, Decimal]]  # 古い順
    kind: str = NumberKind.TREND


def number_stats(event: Event, today: date) -> NumberSum | NumberTrend | None:
    """詳細に出す数字の統計。数字を記録しないイベントなら None。"""
    if event.number_kind == NumberKind.SUM:
        return _sum(event, today)
    if event.number_kind == NumberKind.TREND:
        return _trend(event)
    return None


def _d(value) -> Decimal:
    """合計を、列と同じ小数3桁にそろえる（SQLite は合計を浮動小数で返す）。"""
    return Decimal(value or 0).quantize(Decimal("0.001"))


def _sum(event: Event, today: date) -> NumberSum:
    logs = _valued(event)
    first = today.year * 12 + today.month - SUM_MONTHS  # 12か月前の月（0始まりの通し番号）
    start = date(first // 12, first % 12 + 1, 1)
    by_month = {
        (row["y"], row["m"]): _d(row["s"])
        for row in logs.filter(local_date__gte=start)
        .annotate(y=ExtractYear("local_date"), m=ExtractMonth("local_date"))
        .values("y", "m")
        .annotate(s=Sum("value"))
        .order_by()
    }
    keys = [((first + i) // 12, (first + i) % 12 + 1) for i in range(SUM_MONTHS)]
    all_time = logs.aggregate(s=Sum("value"), n=Count("id"))
    return NumberSum(
        unit=event.number_unit,
        month=by_month.get((today.year, today.month), _ZERO),
        year=_d(logs.filter(local_date__year=today.year).aggregate(s=Sum("value"))["s"]),
        total=_d(all_time["s"]),
        count=all_time["n"],
        months=[(y, m, by_month.get((y, m), _ZERO)) for y, m in keys],
    )


def _trend(event: Event) -> NumberTrend:
    recent = list(_valued(event).values_list("local_date", "value")[:TREND_POINTS])  # 新しい順
    points = recent[::-1]
    values = [v for _, v in points]
    if not values:
        return NumberTrend(event.number_unit, None, None, None, None, None, 0, [])
    average = (sum(values) / len(values)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return NumberTrend(
        unit=event.number_unit,
        latest=values[-1],
        diff=values[-1] - values[-2] if len(values) >= 2 else None,
        average=average,
        lowest=min(values),
        highest=max(values),
        count=len(values),
        points=points,
    )
