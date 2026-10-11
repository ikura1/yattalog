"""連続記録の計算と表示状態（決定 014・015・032）。"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from apps.events.models import StreakUnit
from apps.events.services.dates import period_index

STREAK_MIN = 2  # 2期間以上続いたらバッジを出す

UNIT_WORD = {StreakUnit.DAY: "日", StreakUnit.WEEK: "週", StreakUnit.MONTH: "か月"}
CURRENT_WORD = {StreakUnit.DAY: "今日", StreakUnit.WEEK: "今週", StreakUnit.MONTH: "今月"}


def compute_streak(dates_desc: Iterable[date], unit: str) -> tuple[int, int | None]:
    """新しい順の記録の日付から、(連続回数, 連続の最後の期間の番号) を返す。

    最新の期間から遡り、記録がある期間が途切れたところで止まる。
    同じ期間の記録は1回と数える。
    """
    if unit == StreakUnit.NONE:
        return (0, None)
    count = 0
    last: int | None = None
    prev: int | None = None
    for d in dates_desc:
        p = period_index(d, unit)
        if prev is None:
            last, prev, count = p, p, 1
            continue
        if p == prev:
            continue
        if p == prev - 1:
            count += 1
            prev = p
            continue
        break
    return (count, last)


@dataclass(frozen=True)
class StreakState:
    count: int
    current: bool  # 今の期間に記録がある（False なら「今の期間はまだ」）
    unit: str

    @property
    def text(self) -> str:
        return f"{self.count}{UNIT_WORD[self.unit]}連続"

    @property
    def pending_text(self) -> str:
        return f"（{CURRENT_WORD[self.unit]}はまだ）"


def streak_state(streak_count: int, streak_period: int | None, unit: str, today: date) -> StreakState | None:
    """キャッシュと今日の日付から、バッジを出すかどうかと出し方を決める。

    - 連続の最後の期間 ＝ 今の期間 → 連続中
    - 連続の最後の期間 ＝ 今の期間 − 1 → 今の期間はまだ（控えめに表示）
    - それ以外 → 途切れている（出さない）
    """
    if unit == StreakUnit.NONE or streak_period is None or streak_count < STREAK_MIN:
        return None
    now = period_index(today, unit)
    if streak_period == now:
        return StreakState(streak_count, True, unit)
    if streak_period == now - 1:
        return StreakState(streak_count, False, unit)
    return None
