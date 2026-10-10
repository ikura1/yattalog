"""画面に出す値を組み立てる（サービス層の結果 → テンプレート用の値）。"""

from dataclasses import dataclass
from datetime import date

from apps.events.models import Event
from apps.events.services.dates import elapsed
from apps.events.services.streaks import StreakState, streak_state


@dataclass(frozen=True)
class Tile:
    event: Event
    number: str
    unit: str
    is_today: bool
    never: bool
    streak: StreakState | None

    @property
    def streak_unit_label(self) -> str:
        if not self.streak or self.streak.unit == "day":
            return ""
        return {"week": "週", "month": "か月"}[self.streak.unit]

    @property
    def aria_label(self) -> str:
        e = self.event
        if self.never:
            state = "まだ記録なし"
        elif self.is_today:
            state = "今日やった"
        else:
            state = f"前回から{self.number}{self.unit}"
        s = f"{e.name}、{state}"
        if self.streak:
            s += f"、{self.streak.text}" + ("" if self.streak.current else self.streak.pending_text)
        return s + "。ダブルタップで記録"


def tile(event: Event, today: date) -> Tile:
    el = elapsed(event.last_local_date, today)
    number, unit = el.label
    return Tile(
        event=event,
        number=number,
        unit=unit,
        is_today=el.days == 0,
        never=el.days is None,
        streak=streak_state(event.streak_count, event.streak_period, event.streak_unit, today),
    )
