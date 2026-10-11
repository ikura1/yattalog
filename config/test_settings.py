"""テスト用の設定。開発用の既定値（SQLite・DEBUG）で動かす。"""

import os

os.environ.setdefault("DJANGO_DEBUG", "1")

from config.settings import *  # noqa: E402, F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # noqa: S303
