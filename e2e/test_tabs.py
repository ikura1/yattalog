"""カテゴリのタブ（「カテゴリなし」、決定 050）。"""

import pytest
from playwright.sync_api import expect

from apps.events.services import events as ev_svc

pytestmark = pytest.mark.e2e


def test_カテゴリなしのタブで_カテゴリに入っていないイベントだけを見られる(logged_in_page, user):
    house = ev_svc.create_category(user, "家事")
    ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf", category_id=house.id)
    ev_svc.create_event(user, name="散髪", emoji="✂️", color="grape")
    page = logged_in_page
    page.goto(page.base_url + "/")

    page.get_by_role("tab", name="カテゴリなし").click()

    expect(page.locator("#grid .tile", has_text="散髪")).to_be_visible()
    expect(page.locator("#grid .tile", has_text="水やり")).to_be_hidden()

    page.locator("#addTile").click()
    expect(page.locator('#sheet input[name="category"][value=""]')).to_be_checked()
    page.locator("#evName").fill("歯医者")
    page.get_by_role("button", name="追加する").click()

    expect(page.locator("#grid .tile", has_text="歯医者")).to_be_visible()
    expect(page.get_by_role("tab", name="カテゴリなし")).to_have_attribute("aria-selected", "true")
    expect(page.get_by_role("tab", name="カテゴリなし").locator(".n")).to_have_text("2")
