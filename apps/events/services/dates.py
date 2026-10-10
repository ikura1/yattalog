"""日付の計算。すべて記録の日付（local_date）と「ユーザーの今のタイムゾーンでの今日」で行う（決定 026）。"""

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apps.core import clock
from apps.events.models import StreakUnit

DEFAULT_TZ = "Asia/Tokyo"


def is_valid_timezone(tz_name: str) -> bool:
    """IANA のタイムゾーン名として正しいか。"""
    if not tz_name or len(tz_name) > 64:
        return False
    try:
        ZoneInfo(tz_name)
    except ZoneInfoNotFoundError, ValueError:
        return False
    return True


def zone(tz_name: str) -> ZoneInfo:
    """表示・計算用。保存済みの値が壊れていても落ちないよう、正しくなければ既定のタイムゾーンにする。"""
    return ZoneInfo(tz_name) if is_valid_timezone(tz_name) else ZoneInfo(DEFAULT_TZ)


def now_utc() -> datetime:
    return clock.now()


def today_in(tz_name: str, now: datetime | None = None) -> date:
    return (now or now_utc()).astimezone(zone(tz_name)).date()


def period_index(d: date, unit: str) -> int:
    """連続記録の「期間の番号」（決定 015・032）。

    - day: 日付の通し番号
    - week: 月曜始まりの週の通し番号
    - month: 年×12＋月
    """
    if unit == StreakUnit.DAY:
        return d.toordinal()
    if unit == StreakUnit.WEEK:
        # date.toordinal() は 0001-01-01（月曜）が 1。月曜始まりの週にそろえる
        return (d.toordinal() - 1) // 7
    if unit == StreakUnit.MONTH:
        return d.year * 12 + (d.month - 1)
    raise ValueError(f"unknown streak unit: {unit}")


@dataclass(frozen=True)
class Elapsed:
    """タイルに出す経過日数（SPEC 3.3）。"""

    days: int | None  # None は一度も記録していない

    @property
    def label(self) -> tuple[str, str]:
        """(数字, 単位)。例：("5", "日")、("今日", "")、("—", "")。"""
        d = self.days
        if d is None:
            return ("—", "")
        if d <= 0:
            return ("今日", "")
        if d < 60:
            return (str(d), "日")
        if d < 730:
            return (str(d // 30), "か月")
        return (str(d // 365), "年")


def elapsed(last_local_date: date | None, today: date) -> Elapsed:
    if last_local_date is None:
        return Elapsed(None)
    # タイムゾーンをまたいだ直後は、記録の日付が「今日」より先になることがある。その場合は「今日」とする
    return Elapsed(max(0, (today - last_local_date).days))


def friendly_interval(days: float) -> str:
    """平均間隔を丸めた文章（SPEC 3.5）。"""
    if days < 1.5:
        return "ほぼ毎日"
    if days < 10:
        return f"だいたい{round(days)}日ごと"
    if days < 45:
        return f"だいたい{round(days / 7)}週間ごと"
    if days < 365:
        return f"だいたい{round(days / 30)}か月ごと"
    return f"だいたい{round(days / 365)}年ごと"
