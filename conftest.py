import os

os.environ.setdefault("DJANGO_DEBUG", "1")

import freezegun  # noqa: E402
import pytest  # noqa: E402

from apps.core.testing import NOW, new_user  # noqa: E402

freezegun.configure(extend_ignore_list=["hypothesis", "playwright", "greenlet", "asyncio"])


@pytest.fixture(autouse=True)
def frozen_clock(request):
    """時計を NOW に固定する。ブラウザを動かす E2E テスト（e2e マーク）では固定しない。"""
    if request.node.get_closest_marker("e2e"):
        yield
        return
    with freezegun.freeze_time(NOW):
        yield


@pytest.fixture(autouse=True)
def empty_cache():
    """レート制限の回数がテストをまたいで残らないようにする。"""
    from django.core.cache import cache

    cache.clear()
    yield


@pytest.fixture
def user(db):
    return new_user()


@pytest.fixture
def other_user(db):
    return new_user(email="b@example.com")
