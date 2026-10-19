"""ログイン中の画面を、ブラウザに保存させない（2026-10-19）。

共用の端末で、ログアウトのあと「戻る」やブラウザのキャッシュから、前の人の画面が見えないようにする。
以前はログアウトのときに Clear-Site-Data: "cache" で消させていたが、Chrome などは消去に数秒かかり、
ログアウトが止まったように見えた。はじめから保存させなければ、消す必要がない。
"""

from django.utils.cache import patch_cache_control


class PrivatePagesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            patch_cache_control(response, private=True, no_store=True)
        return response
