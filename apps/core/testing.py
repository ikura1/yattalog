"""テストで共有する定数とファクトリ（conftest を import しないためのモジュール、レビュー2回目 #2）。"""

from datetime import UTC, date, datetime

# テストの時計は1つだけ。日本時間 2026-10-10（土）12:00
NOW = datetime(2026, 10, 10, 3, 0, tzinfo=UTC)
TODAY = date(2026, 10, 10)


def new_user(email: str = "a@example.com", tz: str = "Asia/Tokyo"):
    from apps.accounts.models import User
    from apps.spaces.services import ensure_personal_space

    user = User.objects.create_user(email=email, timezone=tz)
    ensure_personal_space(user)
    return user
