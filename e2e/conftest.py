"""ブラウザを動かす E2E テスト（レビュー2回目 #4）。

`uv run pytest -m e2e` で実行する（通常の `pytest` では動かない）。
楽観的更新・取り消し・失敗時の巻き戻しは JS が担っているので、サーバーのテストだけでは確かめられない。
"""

import os

import pytest
from django.conf import settings
from django.test import Client

from apps.events.services import events

# Playwright の同期 API はイベントループ上で動くので、同じスレッドの ORM を Django が止める。テストに限り許可する
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """ブラウザのタイムゾーンを、利用者の既定（Asia/Tokyo）にそろえる。

    ホームを開くと、アプリは端末のタイムゾーンに合わせて利用者の設定を変える（決定 023）。ブラウザが UTC のままだと、
    日本時間の 0〜9時に流したとき、テストが作った「今日」とアプリの「今日」がずれて落ちる。
    """
    return {**browser_context_args, "timezone_id": "Asia/Tokyo"}


@pytest.fixture
def logged_in_page(page, live_server, transactional_db, user):
    """Google ログインを通らず、セッションを直接作ってブラウザに渡す。"""
    client = Client()
    client.force_login(user)
    session_id = client.cookies[settings.SESSION_COOKIE_NAME].value
    page.context.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": session_id, "url": live_server.url}])
    page.base_url = live_server.url
    return page


@pytest.fixture
def home(logged_in_page, user):
    events.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week")
    page = logged_in_page
    page.goto(page.base_url + "/")
    return page
