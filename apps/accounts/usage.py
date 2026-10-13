"""利用状況の集計（成功の基準を測る、決定 051）。

出すのは人数と件数だけ。だれが使っているか、何を記録しているかは出さない。
外部の分析ツールには送らず、自分の DB を数える。
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median

from django.db.models import Count

from apps.accounts.models import User
from apps.events.models import Event, Log

SETTLED_AFTER = timedelta(days=14)  # 登録からこれだけたった人を、「続けているか」の対象にする
ACTIVE_WITHIN = timedelta(days=7)  # 直近これだけの間に記録していれば、「使っている」
GOAL = 5  # β の成功の基準：続けて使っている人が、20人中5人以上


@dataclass(frozen=True)
class UsageSummary:
    users: int  # 登録している人（利用を止めた人を除く）
    active_7d: int  # 直近7日に1回以上記録した人
    settled: int  # 登録から2週間以上たった人
    retained: int  # そのうち、直近7日に1回以上記録した人（＝続けて使っている人）
    median_events: int | None  # 1人あたりのイベント数（まん中の人の値）
    logs: int  # 記録の総数
    goal: int = GOAL

    @property
    def retained_percent(self) -> int | None:
        return round(self.retained * 100 / self.settled) if self.settled else None

    @property
    def goal_met(self) -> bool:
        return self.retained >= self.goal


def usage_summary(now: datetime) -> UsageSummary:
    users = User.objects.filter(is_active=True)
    # 「記録した」は、記録の日付ではなく、実際に操作した時刻で見る（過去の日付での記録を、最近の利用と数えるため）
    recent = Log.objects.filter(created_at__gte=now - ACTIVE_WITHIN, space__members__user__is_active=True)
    active_ids = set(recent.values_list("space__members__user", flat=True))
    settled_ids = set(users.filter(created_at__lte=now - SETTLED_AFTER).values_list("id", flat=True))
    per_user = dict(
        Event.objects.filter(space__members__user__is_active=True)
        .values_list("space__members__user")
        .annotate(n=Count("id"))
    )
    total = users.count()
    counts = [per_user.get(uid, 0) for uid in users.values_list("id", flat=True)]
    return UsageSummary(
        users=total,
        active_7d=len(active_ids),
        settled=len(settled_ids),
        retained=len(active_ids & settled_ids),
        median_events=round(median(counts)) if counts else None,
        logs=Log.objects.filter(space__members__user__is_active=True).count(),
    )
