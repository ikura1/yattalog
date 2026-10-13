"""ホームでの1タップ記録（決定 028：楽観的更新と取り消し）と、上限に達したときの知らせ。"""

import re

import pytest
from playwright.sync_api import expect

from apps.events.models import Log
from e2e.pages import tile

pytestmark = pytest.mark.e2e


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
    # 「さっき」は返事を待たずに出る（楽観的更新）。サーバーが書き終わったことは、成功のトーストで確かめる。
    # 待たずに DB を読むと、書き込みの途中にぶつかって SQLite が「table is locked」を返すことがある（#52）
    expect(page.locator(".toast:not(.hint)")).to_contain_text("シーツ交換 を記録しました")
    assert Log.objects.count() == 1


def test_操作が多すぎると言われたら_その旨を知らせてタイルを元に戻す(home):
    page = home
    page.route(
        "**/record/", lambda route: route.fulfill(status=429, body="操作が多すぎます", headers={"Retry-After": "30"})
    )

    tile(page).click()

    expect(page.locator(".toast:not(.hint)")).to_contain_text("操作が多すぎます")
    expect(tile(page).locator(".ago")).to_have_text("まだ")
