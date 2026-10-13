"""利用状況の集計（成功の基準を測る、決定 051）。出すのは人数と件数だけで、だれが、は出さない。"""

import uuid
from datetime import timedelta

import pytest
from django.test import Client, override_settings

from apps.accounts.services import sync_admin_flag
from apps.accounts.tests.test_admin_access import ADMIN, BOSS, enroll
from apps.accounts.usage import usage_summary
from apps.core.testing import NOW, new_user
from apps.events.models import Log
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc

USAGE = "/admin/usage/"


def member(email, joined_days_ago, last_record_days_ago=None, events=1):
    """登録した日と、最後に記録した日を決めて、ユーザーを作る。"""
    user = new_user(email=email)
    type(user).objects.filter(pk=user.pk).update(created_at=NOW - timedelta(days=joined_days_ago))
    made = [ev_svc.create_event(user, name=f"e{i}", emoji="⭐", color="sky") for i in range(events)]
    if last_record_days_ago is not None:
        result = log_svc.record(user, made[0].id, uuid.uuid7())
        Log.objects.filter(pk=result.log.pk).update(created_at=NOW - timedelta(days=last_record_days_ago))
    return user


@pytest.mark.django_db
def test_だれもいなければ_すべて0で_割合は出さない():
    s = usage_summary(NOW)
    assert (s.users, s.active_7d, s.settled, s.retained, s.logs) == (0, 0, 0, 0, 0)
    assert s.retained_percent is None and s.median_events is None


@pytest.mark.django_db
def test_続けて使っている人は_登録から2週間以上たち_直近7日に記録した人():
    member("a@example.com", joined_days_ago=30, last_record_days_ago=1)  # 続けている
    member("b@example.com", joined_days_ago=30, last_record_days_ago=10)  # 最近は記録していない
    member("c@example.com", joined_days_ago=30)  # 一度も記録していない
    member("d@example.com", joined_days_ago=3, last_record_days_ago=0)  # 登録したばかり（まだ数えない）

    s = usage_summary(NOW)

    assert (s.users, s.settled, s.retained) == (4, 3, 1)
    assert s.active_7d == 2  # a と d
    assert s.retained_percent == 33


@pytest.mark.django_db
def test_目標に届いたかどうかが分かる():
    for i in range(5):
        member(f"u{i}@example.com", joined_days_ago=20, last_record_days_ago=2)

    s = usage_summary(NOW)

    assert (s.retained, s.goal, s.goal_met) == (5, 5, True)
    assert usage_summary(NOW - timedelta(days=30)).goal_met is False


@pytest.mark.django_db
def test_イベント数は_まん中の人の値で出す_件数は合計():
    member("a@example.com", 30, 1, events=1)
    member("b@example.com", 30, 1, events=3)
    member("c@example.com", 30, 1, events=10)

    s = usage_summary(NOW)

    assert (s.median_events, s.logs) == (3, 3)


@pytest.mark.django_db
def test_利用を止めた人は_数えない():
    stopped = member("x@example.com", 30, 1)
    type(stopped).objects.filter(pk=stopped.pk).update(is_active=False)

    assert usage_summary(NOW).users == 0


# --- 管理画面 ---


@pytest.fixture
def inside():
    with override_settings(ADMIN_EMAILS=[BOSS]):
        boss = sync_admin_flag(new_user(email=BOSS))
        client = Client()
        client.force_login(boss)
        enroll(client, boss)
        yield client


@pytest.mark.django_db
def test_利用状況は_管理画面の中でだけ見られる(client, user):
    assert "/login/" in client.get(USAGE)["Location"]
    client.force_login(user)
    assert client.get(USAGE).status_code == 404


@pytest.mark.django_db
def test_利用状況には_人数と件数だけが出て_だれかは出ない(inside):
    member("secret-person@example.com", joined_days_ago=30, last_record_days_ago=1)

    body = inside.get(USAGE).content.decode()

    assert "続けて使っている人" in body and "目標" in body
    assert "secret-person@example.com" not in body


@pytest.mark.django_db
def test_管理画面の入口から_利用状況へ行ける(inside):
    assert f'href="{USAGE}"' in inside.get(ADMIN).content.decode()


# --- 登録できる人数の上限を、設定で変えられる（費用が上限を超えそうなときに、登録を止める。決定 052） ---


@pytest.mark.parametrize("value,expected", [("7", 7), ("", 20), (None, 20), ("  12 ", 12)])
def test_上限は環境変数で変えられ_空なら既定の20人(value, expected):
    from config.settings import max_users_from

    assert max_users_from(value) == expected


def test_デプロイのときに_上限の値を渡している():
    from pathlib import Path

    from django.conf import settings

    workflow = (Path(settings.BASE_DIR) / ".github" / "workflows" / "deploy.yml").read_text()
    assert "YATTALOG_MAX_USERS=${{ vars.MAX_USERS }}" in workflow
