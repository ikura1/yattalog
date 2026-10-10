import os

os.environ.setdefault("DJANGO_DEBUG", "1")

from datetime import UTC, date, datetime  # noqa: E402

import freezegun  # noqa: E402
import pytest  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.spaces.services import ensure_personal_space  # noqa: E402

# テストの時計は1つだけ（レビュー 5）。日本時間 2026-10-10（土）12:00 に固定する
NOW = datetime(2026, 10, 10, 3, 0, tzinfo=UTC)
TODAY = date(2026, 10, 10)

freezegun.configure(extend_ignore_list=["hypothesis"])


@pytest.fixture(autouse=True)
def frozen_clock():
    with freezegun.freeze_time(NOW):
        yield


def new_user(email="a@example.com", tz="Asia/Tokyo") -> User:
    user = User.objects.create_user(email=email, timezone=tz)
    ensure_personal_space(user)
    return user


@pytest.fixture
def user(db):
    return new_user()


@pytest.fixture
def other_user(db):
    return new_user(email="b@example.com")
