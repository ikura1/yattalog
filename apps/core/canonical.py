"""独自のドメインへ寄せる（決定 064）。

古いホスト（Cloud Run の run.app）に来た人を、同じ道のりのまま独自のドメインへ 301 で送る。
寄せ先は環境変数 YATTALOG_CANONICAL_HOST（GitHub の Variable CANONICAL_HOST）。空なら何もしない。
Google ログインの戻り先に新しいドメインを足してから入れること（先に入れると、ログインできなくなる）。
"""

from django.conf import settings
from django.http import HttpRequest, HttpResponsePermanentRedirect

# 死活監視は、どちらのホストでも答える。書き込み（POST など）は送らない（301 でやり直すと、中身が消えるため）
KEEP_PATHS = {"/health"}
SAFE_METHODS = {"GET", "HEAD"}


class CanonicalHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        canonical = settings.CANONICAL_HOST
        if (
            canonical
            and request.method in SAFE_METHODS
            and request.path not in KEEP_PATHS
            and request.get_host() != canonical
        ):
            return HttpResponsePermanentRedirect(f"https://{canonical}{request.get_full_path()}")
        return self.get_response(request)
