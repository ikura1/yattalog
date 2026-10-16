"""実績バッジ（SPEC 3.10、決定 063）。"""

import pytest
from playwright.sync_api import expect

from e2e.pages import tile

pytestmark = pytest.mark.e2e


def test_はじめて記録すると_知らせに実績が添えられ_メニューの実績で見られる(home):
    page = home
    tile(page).click()

    expect(page.locator("#toast-root")).to_contain_text("🏅 実績解除：はじめの一歩")

    page.get_by_role("button", name="メニュー").click()
    page.get_by_role("button", name="実績", exact=False).first.click()
    sheet = page.locator("#sheet-body")
    expect(sheet.get_by_role("heading", name="実績")).to_be_visible()
    expect(sheet).to_contain_text("1 / 15")
    expect(sheet.locator("li.on")).to_contain_text("はじめの一歩")


def test_メニューから開いたシートは_一番上から見える(home):
    """メニューが少しスクロールした状態のまま中身が入れ替わり、見出しが切れていた。"""
    page = home
    page.set_viewport_size({"width": 390, "height": 600})
    page.get_by_role("button", name="メニュー").click()
    page.locator("#sheet").evaluate("s => { s.scrollTop = 80; }")
    page.get_by_role("button", name="実績", exact=False).first.click()
    expect(page.locator("#sheet-body .ach")).to_be_visible()
    assert page.locator("#sheet").evaluate("s => s.scrollTop") == 0
