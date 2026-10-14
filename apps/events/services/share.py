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
MILESTONES = (10, 30, 50, 100)  # これと、100回を超えたら100回ごとに、お祝いの印を付ける


@dataclass(frozen=True)
class ShareInfo:
    log: Log
    event: Event
    headline: str  # 「🔥 5週連続」「24回目」「はじめての記録」など
    subline: str  # 見出しの下の添え書き。連続記録のときだけ「通算 24回目」
    when: str  # 画像の下に出す日時
    memo: str  # 載せるかどうかは、画面で本人が選ぶ（初期状態では載せない）
    text: str  # 投稿文


def is_milestone(n: int) -> bool:
    return n in MILESTONES or (n > MILESTONES[-1] and n % 100 == 0)


def _headline(log: Log) -> tuple[str, str]:
    """見出しと添え書き。その記録の時点で決める（あとの記録には左右されない）。

    どんなときでも前向きに読めるものだけを出す（決定 053 の追記）。
    「40日ぶり」は、サボっていたように読めるので使わない。
    連続記録 → はじめての記録 → 通算の何回目か。
    """
    event = log.event
    until = Log.objects.filter(event=event, local_date__lte=log.local_date)
    earlier = Q(local_date__lt=log.local_date) | Q(local_date=log.local_date, created_at__lt=log.created_at)
    earlier |= Q(local_date=log.local_date, created_at=log.created_at, id__lt=log.id)
    nth = until.filter(earlier).count() + 1
    dates = until.order_by("-local_date").values_list("local_date", flat=True).distinct()
    count, _ = compute_streak(dates.iterator(), event.streak_unit)
    if count >= STREAK_MIN:
        return f"🔥 {count}{UNIT_WORD[event.streak_unit]}連続", f"通算 {nth}回目"
    if nth == 1:
        return "はじめての記録", ""
    return f"{'🎉 ' if is_milestone(nth) else ''}{nth}回目", ""


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
    headline, subline = _headline(log)
    detail = f"{headline}（{subline}）" if subline else headline
    text = f"{event.emoji} {event.name} やった！ {detail} {HASHTAG} {site_url}"
    return ShareInfo(
        log=log, event=event, headline=headline, subline=subline, when=_when(log), memo=log.memo, text=text
    )
