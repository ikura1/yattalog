from django.conf import settings


def analytics(request):
    """アクセス解析のサイト ID（決定 047）。空ならどの画面でも読み込まない。"""
    return {"umami_website_id": settings.UMAMI_WEBSITE_ID}
