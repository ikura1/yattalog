"""押した瞬間の反応（2026-10-20）。サーバーの返事を待たずに、シートを開く・見た目を試す。"""

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_メニューを押すと_返事を待たずにシートが開き_届いたら中身に変わる(home):
    page = home
    held = []
    page.route("**/menu/", lambda route: held.append(route))  # 返事を止めておく

    page.get_by_role("button", name="メニュー").click()

    expect(page.locator("#sheet")).to_be_visible()
    expect(page.locator("#sheet-body .sheet-loading")).to_have_count(1)
    held[0].continue_()
    expect(page.get_by_role("heading", name="メニュー")).to_be_visible()
    expect(page.locator("#sheet-body .sheet-loading")).to_have_count(0)


def test_返事が届かなければ_シートを閉じて知らせる(home):
    page = home
    page.route("**/menu/", lambda route: route.abort())
    page.get_by_role("button", name="メニュー").click()
    expect(page.locator("#toast-root")).to_contain_text("通信できませんでした")
    expect(page.locator("#sheet")).to_be_hidden()


def test_見た目は_選んだ時点で試せて_保存せずに閉じると元に戻る(home, user):
    page = home
    page.get_by_role("button", name="メニュー").click()
    page.locator("#sheet-body .menu-card button", has_text="週の始まり").click()

    page.get_by_text("暗い", exact=True).click()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")  # 保存しなくても、すぐ変わる

    page.keyboard.press("Escape")
    expect(page.locator("html")).not_to_have_attribute("data-theme", "dark")  # 保存せずに閉じたら元どおり
    user.refresh_from_db()
    assert user.theme == "auto"


def test_見た目を選んで保存すれば_そのまま残る(home, user):
    page = home
    page.get_by_role("button", name="メニュー").click()
    page.locator("#sheet-body .menu-card button", has_text="週の始まり").click()
    page.get_by_text("明るい", exact=True).click()
    page.get_by_role("button", name="保存する").click()
    expect(page.locator("#toast-root")).to_contain_text("保存しました")
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
