"""はじめて使うときのテンプレート（決定 042）。"""

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_はじめての人は_テンプレートを選んで_すぐ記録を始められる(logged_in_page):
    page = logged_in_page
    page.goto(page.base_url + "/")
    expect(page.locator("#welcome")).to_be_visible()

    page.locator(".starter", has_text="シーツ交換").click()
    page.locator(".starter", has_text="散髪").click()
    page.locator("#welcome").get_by_role("button", name="追加する").click()

    expect(page.locator("#grid .tile .name")).to_have_text(["シーツ交換", "散髪"])
    expect(page.locator("#welcome")).to_have_count(0)
    page.locator("#grid .tile", has_text="散髪").click()
    expect(page.locator("#grid .tile", has_text="散髪").locator(".ago")).to_have_text("さっき")
