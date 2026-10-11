"""時計。現在時刻はここからだけ取る（テストでは freezegun で固定する、レビュー 5）。"""

from datetime import datetime

from django.utils import timezone


def now() -> datetime:
    return timezone.now()
