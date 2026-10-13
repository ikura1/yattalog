"""画面のテストで共有するもの。"""

import pytest

from apps.events.services import events as ev_svc


@pytest.fixture
def client_in(client, user):
    client.raise_request_exception = False  # 500 を例外ではなくレスポンスとして確かめる
    client.force_login(user)
    return client


@pytest.fixture
def event(user):
    return ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week")
