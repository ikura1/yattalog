"""テストで共有する定数とファクトリ（conftest を import しないためのモジュール、レビュー2回目 #2）。"""

import json
from datetime import UTC, date, datetime
from pathlib import Path

# テストの時計は1つだけ。日本時間 2026-10-10（土）12:00
NOW = datetime(2026, 10, 10, 3, 0, tzinfo=UTC)
TODAY = date(2026, 10, 10)


def new_user(email: str = "a@example.com", tz: str = "Asia/Tokyo"):
    from apps.accounts.models import User
    from apps.spaces.services import ensure_personal_space

    user = User.objects.create_user(email=email, timezone=tz)
    ensure_personal_space(user)
    return user


def collect_static(source: Path, root: Path) -> dict[str, str]:
    """本番と同じ入れ物で静的ファイルを集め、元の名前 → ハッシュ入りの名前 の対応を返す。"""
    from django.conf import settings
    from django.core.management import call_command
    from django.test import override_settings

    with override_settings(
        STORAGES={**settings.STORAGES, "staticfiles": {"BACKEND": "apps.core.staticfiles.ModuleStaticFilesStorage"}},
        STATICFILES_FINDERS=["django.contrib.staticfiles.finders.FileSystemFinder"],
        STATICFILES_DIRS=[source],
        STATIC_ROOT=root,
    ):
        call_command("collectstatic", interactive=False, verbosity=0)
    return json.loads((root / "staticfiles.json").read_text())["paths"]
