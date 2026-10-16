"""実績バッジ（SPEC 3.10、決定 020・063）。

定義はここに持ち、データベースには解除の記録（Achievement）だけを残す。記録・編集・イベントの追加のあとに
check() を呼び、新しく解除したものを知らせる。一度解除したら消さない（記録を消しても残す）。
"""

from dataclasses import dataclass
from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, F, Max
from django.db.models.functions import TruncDate

from apps.events.models import Achievement, Event, Log, StreakUnit
from apps.events.services.dates import now_utc, today_in
from apps.events.services.stats import best_streak


@dataclass(frozen=True)
class AchievementDef:
    code: str
    emoji: str
    name: str
    condition: str  # 未解除のときに見せる条件


# 並びは SPEC 3.10 の表のとおり。📷 フォトログ（写真付きで10回）は、写真の機能が入るまで出さない（決定 063）
DEFS = [
    AchievementDef("first", "🌱", "はじめの一歩", "はじめて記録する"),
    AchievementDef("t10", "🔟", "じゅっかい", "全部のイベントの合計で10回記録する"),
    AchievementDef("t100", "💯", "ひゃっかい", "合計100回記録する"),
    AchievementDef("t1000", "🏔️", "せんかい", "合計1000回記録する"),
    AchievementDef("s1", "🔥", "つづいてる", "どれかのイベントで、毎日7日／毎週4週／毎月3か月続ける"),
    AchievementDef("s2", "🔥🔥", "かなりつづいてる", "毎日30日／毎週12週／毎月6か月続ける"),
    AchievementDef("s3", "👑", "ずっとつづいてる", "毎日100日／毎週52週／毎月12か月続ける"),
    AchievementDef("e50", "🎯", "おなじみ", "1つのイベントを50回記録する"),
    AchievementDef("e100", "🥋", "たつじん", "1つのイベントを100回記録する"),
    AchievementDef("collector", "🗂️", "コレクター", "イベントを10個作る"),
    AchievementDef("past", "🕰️", "思い出した", "過去の日付で記録する"),
    AchievementDef("memo", "📝", "メモ魔", "メモ付きで10回記録する"),
    AchievementDef("share", "📣", "シェアデビュー", "はじめてシェアする"),
    AchievementDef("longgap", "👋", "ひさしぶり", "前回から365日以上空けて記録する"),
    AchievementDef("busy", "🐝", "大忙し", "1日に5種類のイベントを記録する"),
]
BY_CODE = {d.code: d for d in DEFS}

TOTALS = [(1, "first"), (10, "t10"), (100, "t100"), (1000, "t1000")]
PER_EVENT = [(50, "e50"), (100, "e100")]
# 連続記録の目標（単位ごと）。上の段を満たしたら、下の段もすべて満たしている
STREAK_GOALS = [
    ("s1", {StreakUnit.DAY: 7, StreakUnit.WEEK: 4, StreakUnit.MONTH: 3}),
    ("s2", {StreakUnit.DAY: 30, StreakUnit.WEEK: 12, StreakUnit.MONTH: 6}),
    ("s3", {StreakUnit.DAY: 100, StreakUnit.WEEK: 52, StreakUnit.MONTH: 12}),
]
COLLECTOR = 10
MEMOS = 10
LONG_GAP = 365
BUSY_KINDS = 5


def streak_level(unit: str, count: int) -> str | None:
    """連続回数が届いている一番上の段（「s2」など）。"""
    level = None
    for code, goals in STREAK_GOALS:
        if unit in goals and count >= goals[unit]:
            level = code
    return level


def _streak_codes(unit: str, count: int) -> set[str]:
    level = streak_level(unit, count)
    if level is None:
        return set()
    order = [code for code, _ in STREAK_GOALS]
    return set(order[: order.index(level) + 1])


def _gap_before(log: Log) -> int | None:
    """同じイベントの、この記録より前の記録からの日数。"""
    previous = Log.objects.filter(event_id=log.event_id, local_date__lt=log.local_date).aggregate(d=Max("local_date"))[
        "d"
    ]
    return (log.local_date - previous).days if previous else None


def _has_long_gap(events) -> bool:
    for event in events:
        dates = list(
            Log.objects.filter(event=event).values_list("local_date", flat=True).distinct().order_by("local_date")
        )
        if any((b - a).days >= LONG_GAP for a, b in zip(dates, dates[1:], strict=False)):
            return True
    return False


def _satisfied(user, log: Log | None, full: bool) -> set[str]:
    """いま満たしている実績。full なら、過去の記録をすべて見直す（最初の判定）。log は、いま記録したもの。"""
    logs = Log.objects.filter(space__members__user=user)
    events = list(Event.objects.filter(space__members__user=user))
    found: set[str] = set()

    total = logs.count()
    found |= {code for n, code in TOTALS if total >= n}
    most = max((e.log_count for e in events), default=0)
    found |= {code for n, code in PER_EVENT if most >= n}
    if len(events) >= COLLECTOR:
        found.add("collector")
    if logs.exclude(memo="").count() >= MEMOS:
        found.add("memo")
    for event in events:
        count = best_streak(event) if full else event.streak_count
        found |= _streak_codes(event.streak_unit, count)
    busy = logs.values("local_date").annotate(k=Count("event", distinct=True)).filter(k__gte=BUSY_KINDS)
    if busy.exists():
        found.add("busy")

    if log is not None:
        # 記録した日（端末のタイムゾーン）より前の日付なら「過去の日付で記録した」
        if log.local_date < today_in(user.timezone, log.created_at):
            found.add("past")
        gap = _gap_before(log)
        if gap is not None and gap >= LONG_GAP:
            found.add("longgap")
    if full:
        # 最初の判定では、過去の記録から探す。タイムゾーンまでは見ないので、日付の境目では取りこぼすことがある
        if logs.filter(local_date__lt=TruncDate(F("created_at"))).exists():
            found.add("past")
        if _has_long_gap(events):
            found.add("longgap")
    return found


def _unlock(user, codes: set[str], now: datetime) -> list[AchievementDef]:
    have = set(Achievement.objects.filter(user=user).values_list("code", flat=True))
    new = [d for d in DEFS if d.code in codes - have]
    Achievement.objects.bulk_create(
        [Achievement(user=user, code=d.code, unlocked_at=now) for d in new], ignore_conflicts=True
    )
    return new


@transaction.atomic
def check(user, log: Log | None = None, now: datetime | None = None) -> list[AchievementDef]:
    """満たした実績を解除し、新しく解除したもの（知らせる対象）を返す。

    機能が入る前から使っている人（achievements_synced が False）は、最初の1回で満たしているものを
    まとめて静かに解除し、何も返さない（一度に10個以上の知らせが出ないように）。
    """
    now = now or now_utc()
    if not user.achievements_synced:
        _unlock(user, _satisfied(user, log, full=True), now)
        get_user_model().objects.filter(pk=user.pk).update(
            achievements_synced=True
        )  # request.user は包まれているので、型から取らない
        user.achievements_synced = True
        return []
    return _unlock(user, _satisfied(user, log, full=False), now)


def unlock_share(user, now: datetime | None = None) -> list[AchievementDef]:
    """シェアした（端末から知らせを受けた）。シェアは端末で完結するので、ここだけは端末からの知らせで解除する。"""
    return _unlock(user, {"share"}, now or now_utc())


def listing(user) -> list[tuple[AchievementDef, datetime | None]]:
    """実績の一覧（定義の順）と、解除した日時（未解除なら None）。"""
    unlocked = dict(Achievement.objects.filter(user=user).values_list("code", "unlocked_at"))
    return [(d, unlocked.get(d.code)) for d in DEFS]


def announcement(found: list[AchievementDef]) -> str:
    """知らせの文言。「🏅 実績解除：じゅっかい・メモ魔」"""
    return f"🏅 実績解除：{'・'.join(d.name for d in found)}" if found else ""
