"""レート制限（レビュー S7、決定 037）。上限を超えたリクエストには 429 を返す。

数え方は「固定の時間枠」。枠（例：1分）ごとに回数を数え、枠が変わると 0 に戻る。
回数はプロセス内のキャッシュに持つので、Cloud Run のインスタンスごとに別々に数える。
最大2台なので、上限は最大で2倍になる。
"""

import re
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse

from apps.core import clock

TOO_MANY = "操作が多すぎます。少し待ってから、もう一度お試しください。"  # static/js/app.js の TOO_MANY と同じ文言
LOGIN_PREFIX = "/accounts/"
RECORD_SUFFIX = "/record/"
EXPORT_PATH = "/export/"
# 開くたびに記録を集計する画面（ふりかえり、イベント詳細、実績）。全体より厳しい上限で数える
STATS_PATH = re.compile(r"^/(review/|achievements/|events/[0-9a-f-]{36}/)$")


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    retry_after: int = 0  # 秒


def client_ip(request: HttpRequest) -> str:
    """接続元の IP アドレス。

    X-Forwarded-For の先頭は送る側が自由に書けるので、Cloud Run（Google のフロントエンド）が末尾に足した値だけを使う。
    """
    forwarded = [part.strip() for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if part.strip()]
    return forwarded[-1] if forwarded else request.META.get("REMOTE_ADDR", "")


def rules_for(request: HttpRequest) -> list[str]:
    """このリクエストに当てはまる上限の名前。細かいものから順に確かめる。"""
    rules = []
    if request.method == "POST" and request.user.is_authenticated:
        if request.path.endswith(RECORD_SUFFIX):
            rules.append("record")
        if request.path == EXPORT_PATH:
            rules.append("export")
        rules.append("write")
    if request.method == "GET" and STATS_PATH.match(request.path):
        rules.append("stats")
    if request.path.startswith(LOGIN_PREFIX):
        rules.append("login")
    rules.append("all")
    return rules


def hit(rule: str, who: str) -> Verdict:
    """1回分を数え、上限の中に収まっているかを返す。"""
    limit, window = settings.RATE_LIMITS[rule]
    now = clock.now().timestamp()
    slot = int(now // window)
    key = f"rl:{rule}:{who}:{slot}"
    cache.add(key, 0, timeout=window)
    try:
        count = cache.incr(key)
    except ValueError:
        # add と incr の間に期限が切れた場合。数え直す
        cache.set(key, 1, timeout=window)
        count = 1
    if count <= limit:
        return Verdict(True)
    return Verdict(False, max(1, int((slot + 1) * window - now)))


def too_many(retry_after: int) -> HttpResponse:
    response = HttpResponse(TOO_MANY, status=429, content_type="text/plain; charset=utf-8")
    response["Retry-After"] = str(retry_after)
    return response


class RateLimitMiddleware:
    """ログインしていれば人ごと、していなければ接続元ごとに数える。AuthenticationMiddleware より後に置く。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        who = f"u:{request.user.pk}" if request.user.is_authenticated else f"ip:{client_ip(request)}"
        for rule in rules_for(request):
            verdict = hit(rule, who)
            if not verdict.allowed:
                return too_many(verdict.retry_after)
        return self.get_response(request)
