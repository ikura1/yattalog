"""設定（決定 066）。保存すると、見た目と震えはその場で変わり、開き直しても残る。"""

import pytest
from playwright.sync_api import expect

from apps.spaces.services import personal_space

pytestmark = pytest.mark.e2e

DARK_BG = "rgb(18, 22, 30)"  # --bg（暗い画面）
LIGHT_BG = "rgb(238, 241, 246)"  # --bg（明るい画面）


def bg(page):
    return page.evaluate("getComputedStyle(document.body).backgroundColor")


def open_settings(page):
    page.get_by_role("button", name="メニュー").click()
    page.get_by_role("button", name="設定", exact=False).filter(has_text="週の始まり").click()
    expect(page.get_by_role("heading", name="設定")).to_be_visible()


def test_端末が明るくても_暗いを選べば暗くなり_震えも止められる(home, user):
    page = home
    page.emulate_media(color_scheme="light")
    assert bg(page) == LIGHT_BG
    open_settings(page)

    page.get_by_text("暗い", exact=True).click()
    page.get_by_text("押したときに震える").click()
    page.get_by_text("日曜", exact=True).click()
    page.get_by_role("button", name="保存する").click()

    expect(page.locator("#toast-root")).to_contain_text("保存しました")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.locator("body")).to_have_attribute("data-haptics", "0")
    assert bg(page) == DARK_BG
    assert personal_space(user).week_start == "sun"

    page.reload()
    assert bg(page) == DARK_BG  # 開き直しても残る


def test_端末が暗くても_明るいを選べば明るくなる(home, user):
    user.theme = "light"
    user.save()
    page = home
    page.emulate_media(color_scheme="dark")
    page.reload()
    assert bg(page) == LIGHT_BG
