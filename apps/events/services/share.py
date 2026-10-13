"""シェア（SPEC 3.8、決定 017・053）。画像に載せる見出しと、投稿文を決める。

画像そのものは、端末（ブラウザの Canvas）で作る。サーバーには画像を送らない。
"""

from dataclasses import dataclass

from django.db.models import Q

from apps.events.models import Event, Log
from apps.events.services.access import log_for
from apps.events.services.dates import zone
from apps.events.services.streaks import STREAK_MIN, UNIT_WORD, compute_streak

HASHTAG = "#Yattalog"


@dataclass(frozen=True)
class ShareInfo:
    log: Log
    event: Event
    headline: str  # 「🔥 5週連続」「40日ぶり」「はじめての記録」など
    when: str  # 画像の下に出す日時
    memo: str  # 載せるかどうかは、画面で本人が選ぶ（初期状態では載せない）
    text: str  # 投稿文


def _headline(log: Log) -> str:
    """見出し。その記録の時点で決める（あとの記録には左右されない）。連続記録 → その日の何回目か → 何日ぶりか。"""
    event = log.event
    until = Log.objects.filter(event=event, local_date__lte=log.local_date)
    dates = until.order_by("-local_date").values_list("local_date", flat=True).distinct()
    count, _ = compute_streak(dates.iterator(), event.streak_unit)
    if count >= STREAK_MIN:
        return f"🔥 {count}{UNIT_WORD[event.streak_unit]}連続"
    same_day = until.filter(local_date=log.local_date)
    earlier = Q(created_at__lt=log.created_at) | Q(created_at=log.created_at, id__lt=log.id)
    nth = same_day.filter(earlier).count() + 1
    if nth >= 2:
        return f"この日{nth}回目"
    before = until.filter(local_date__lt=log.local_date).order_by("-local_date")
    previous = before.values_list("local_date", flat=True).first()
    if previous is None:
        return "はじめての記録"
    return f"{(log.local_date - previous).days}日ぶり"


def _when(log: Log) -> str:
    d = log.local_date
    text = f"{d.year}年{d.month}月{d.day}日"
    if log.occurred_at:
        at = log.occurred_at.astimezone(zone(log.timezone))
        text += f" {at.hour}:{at.minute:02d}"
    return text


def share_info(user, log_id, site_url: str) -> ShareInfo:
    """シェアの材料。ほかの人の記録は Log.DoesNotExist。"""
    log = log_for(user, log_id)
    event = log.event
    headline = _headline(log)
    text = f"{event.emoji} {event.name} やった！ {headline} {HASHTAG} {site_url}"
    return ShareInfo(log=log, event=event, headline=headline, when=_when(log), memo=log.memo, text=text)
