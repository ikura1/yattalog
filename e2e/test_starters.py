"""はじめて使うときのテンプレート（決定 042）。"""

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_はじめての人は_テンプレートを選んで_すぐ記録を始められる(logged_in_page):
    page = logged_in_page
    page.goto(page.base_url + "/")
    expect(page.locator("#welcome")).to_be_visible()

    page.locator(".starter", has_text="シーツ交換").click()
    page.locator(".starter", has_text="美容院").click()
    page.locator("#welcome").get_by_role("button", name="追加する").click()

    expect(page.locator("#grid .tile .name")).to_have_text(["シーツ交換", "美容院"])
    expect(page.locator("#welcome")).to_have_count(0)
    page.locator("#grid .tile", has_text="美容院").click()
    expect(page.locator("#grid .tile", has_text="美容院").locator(".ago")).to_have_text("さっき")


def test_テンプレートの一覧の_自分で作る_から_イベントの追加画面が開く(logged_in_page):
    """一覧のフォームの hx-swap="none" を、ボタンが引き継いで、追加画面の中身が入っていなかった。"""
    page = logged_in_page
    page.goto(page.base_url + "/")
    page.get_by_role("button", name="自分で作る").click()
    expect(page.locator("#evName")).to_be_visible()
