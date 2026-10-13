"""画面に出す文言のそろえ方（レビュー D6・D11、`docs/wording.md`）。"""

import re
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.accounts.tests.test_google_login import GOOGLE_USER, login_and_messages
from apps.core.ratelimit import TOO_MANY
from apps.core.testing import TODAY, new_user
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.logs import When

APP_JS = (Path(settings.BASE_DIR) / "static" / "js" / "app.js").read_text()


def test_操作が多すぎるときの文言は_サーバーと画面で同じ():
    in_js = re.search(r'const TOO_MANY = "([^"]+)"', APP_JS)[1]
    assert in_js == TOO_MANY.rstrip("。")
    assert in_js == "操作が多すぎます。少し待ってから、もう一度お試しください"


def test_未来の日付を断るときは_今日も選べることが伝わる(user):
    """「今日より前」と書くと、今日は選べないように読める。"""
    event = ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf")
    with pytest.raises(ValidationError, match="今日までの日付を選んでください"):
        log_svc.record(user, event.id, uuid.uuid7(), When(date=TODAY + timedelta(1)))


@pytest.mark.django_db
def test_利用を止められた人には_退会ではなく_停止だと伝える(rf):
    """is_active を下ろすのは、管理画面での利用の停止（決定 045）。退会はその場で消える（決定 040）。"""
    stopped = new_user(email=GOOGLE_USER["email"])
    from allauth.socialaccount.models import SocialAccount

    SocialAccount.objects.create(user=stopped, provider="google", uid=GOOGLE_USER["sub"])
    stopped.is_active = False
    stopped.save()

    response, messages = login_and_messages(rf, GOOGLE_USER)

    assert response.url == "/login/"
    assert len(messages) == 1 and "利用を停止しています" in messages[0] and "退会" not in messages[0]


@pytest.mark.parametrize(
    "pattern",
    [
        r'toast\("[^"]*ませんでした"',  # 失敗は「〜できませんでした」
        r'toast\("[^"]*しました"',  # 成功は「〜しました」
    ],
)
def test_トーストの言い方の型が使われている(pattern):
    assert re.search(pattern, APP_JS)


def test_トーストの文末に_句点を付けない():
    """短い知らせなので、句点は付けない（文が2つ以上あるときの、途中の句点はよい）。"""
    endings = re.findall(r'toast\("([^"]+)"', APP_JS)
    assert endings and not [m for m in endings if m.endswith("。")]
