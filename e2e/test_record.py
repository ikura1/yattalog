"""ホームでの1タップ記録（決定 028：楽観的更新と取り消し）。"""

import re

import pytest
from playwright.sync_api import expect

from apps.events.models import Log
from apps.events.services import events as ev_svc

pytestmark = pytest.mark.e2e


@pytest.fixture
def home(logged_in_page, user):
    ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week")
    page = logged_in_page
    page.goto(page.base_url + "/")
    return page


def tile(page):
    return page.locator("#grid .tile", has_text="シーツ交換")


def test_タップするとさっきになり_取り消すと元に戻る(home):
    page = home
    expect(tile(page).locator(".ago")).to_have_text("まだ")

    tile(page).click()
    expect(tile(page).locator(".ago")).to_have_text("さっき")
    toast = page.locator(".toast:not(.hint)")
    expect(toast).to_contain_text("シーツ交換 を記録しました")
    assert Log.objects.count() == 1

    toast.get_by_role("button", name="取り消す").click()
    expect(page.locator(".toast:not(.hint)")).to_have_text(re.compile("取り消しました"))
    expect(tile(page).locator(".ago")).to_have_text("まだ")
    assert Log.objects.count() == 0


def test_サーバーが失敗したらタイルを元に戻して知らせる(home):
    page = home
    page.route("**/record/", lambda route: route.fulfill(status=500, body="boom"))

    tile(page).click()
    expect(page.locator(".toast:not(.hint)")).to_contain_text("記録できませんでした")
    expect(tile(page).locator(".ago")).to_have_text("まだ")
    expect(tile(page)).not_to_have_class(re.compile(r"\btoday\b"))
    assert Log.objects.count() == 0

    page.unroute("**/record/")
    page.locator(".toast:not(.hint)").get_by_role("button", name="もう一度").click()
    expect(tile(page).locator(".ago")).to_have_text("さっき")
    assert Log.objects.count() == 1
