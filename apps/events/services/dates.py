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


def period_index(d: date, unit: str, week_start: str = "mon") -> int:
    """連続記録の「期間の番号」（決定 015・032・066）。

    - day: 日付の通し番号
    - week: 週の通し番号。週の始まりは月曜（既定）か日曜
    - month: 年×12＋月
    """
    if unit == StreakUnit.DAY:
        return d.toordinal()
    if unit == StreakUnit.WEEK:
        # date.toordinal() は 0001-01-01（月曜）が 1。月曜始まりなら 1 を引き、日曜始まりならそのまま割る
        return (d.toordinal() - (1 if week_start == "mon" else 0)) // 7
    if unit == StreakUnit.MONTH:
        return d.year * 12 + (d.month - 1)
    raise ValueError(f"unknown streak unit: {unit}")


@dataclass(frozen=True)
class Elapsed:
    """タイルに出す経過時間（SPEC 3.3）。"""

    days: int | None  # None は一度も記録していない
    minutes: int | None = None  # 今日の時刻ありの記録からの経過分。それ以外は None（決定 034）

    @property
    def label(self) -> tuple[str, str]:
        """(数字, 単位)。例：("5", "日前")、("3", "時間前")、("さっき", "")、("今日", "")、("—", "")。

        単位には「前」を付ける（決定 048）。「1日」だけだと、間隔や期限のようにも読めるため。
        """
        d = self.days
        if d is None:
            return ("—", "")
        if d <= 0:
            if self.minutes is None:
                return ("今日", "")
            if self.minutes < 60:
                return ("さっき", "")
            return (str(self.minutes // 60), "時間前")
        if d < 60:
            return (str(d), "日前")
        if d < 730:
            return (str(d // 30), "か月前")
        return (str(d // 365), "年前")


def elapsed(
    last_local_date: date | None,
    today: date,
    last_occurred_at: datetime | None = None,
    now: datetime | None = None,
) -> Elapsed:
    if last_local_date is None:
        return Elapsed(None)
    # タイムゾーンをまたいだ直後は、記録の日付が「今日」より先になることがある。その場合は「今日」とする
    days = max(0, (today - last_local_date).days)
    if days > 0 or last_occurred_at is None or now is None:
        return Elapsed(days)
    # 端末とサーバーの時計のずれで、記録の時刻が少し先になることがある。その場合は 0 分とする
    return Elapsed(0, max(0, int((now - last_occurred_at).total_seconds() // 60)))


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
