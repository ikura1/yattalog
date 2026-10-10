import os

os.environ.setdefault("DJANGO_DEBUG", "1")

import pytest  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.spaces.services import ensure_personal_space  # noqa: E402


@pytest.fixture
def make_user(db):
    def _make(email="a@example.com", tz="Asia/Tokyo"):
        user = User.objects.create_user(email=email, timezone=tz)
        ensure_personal_space(user)
        return user

    return _make


@pytest.fixture
def user(make_user):
    return make_user()


@pytest.fixture
def other_user(make_user):
    return make_user(email="b@example.com")
