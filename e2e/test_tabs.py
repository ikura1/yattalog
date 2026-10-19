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


@pytest.mark.parametrize("width", [320, 390])
def test_スマホの幅でも_カテゴリの管理で名前が読める(home, user, width):
    ev_svc.create_category(user, "からだのメンテナンス")
    page = home
    page.set_viewport_size({"width": width, "height": 640})
    page.reload()
    page.get_by_label("カテゴリを編集").click()
    name = page.locator(".catlist input[name=name]")
    expect(name).to_be_visible()
    # 10文字（全角）が切れずに入る幅。ボタンと同じ行に並べると、320px の画面では 75px しか残らない
    assert name.bounding_box()["width"] >= 200
    # 並べ替えと削除のボタンは、画面からはみ出さない
    delete = page.get_by_label("からだのメンテナンスを削除").bounding_box()
    assert delete["x"] + delete["width"] <= width


def names(page):
    return page.locator("#sheet-body .catlist > li[data-id] input[name=name]").evaluate_all(
        "els => els.map(e => e.value)"
    )


def test_カテゴリは_取っ手をドラッグして並べ替えられ_タブにも反映される(home, user):
    for n in ("家のこと", "身だしなみ", "からだ"):
        ev_svc.create_category(user, n)
    page = home
    page.reload()
    page.get_by_label("カテゴリを編集").click()
    handle = page.get_by_label("「からだ」を並べ替え（↑↓キーでも動かせます）")
    target = page.locator("#sheet-body .catlist > li[data-id]").first

    box, top = handle.bounding_box(), target.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2, top["y"] + 5, steps=8)
    page.mouse.up()

    assert names(page) == ["からだ", "家のこと", "身だしなみ"]
    expect(page.locator("#tabs [data-tab]").nth(1)).to_contain_text("からだ")
    assert [c.name for c in ev_svc.list_categories(user)] == ["からだ", "家のこと", "身だしなみ"]


def test_カテゴリは_取っ手で上下のキーを押しても並べ替えられる(home, user):
    for n in ("家のこと", "身だしなみ"):
        ev_svc.create_category(user, n)
    page = home
    page.reload()
    page.get_by_label("カテゴリを編集").click()
    handle = page.get_by_label("「身だしなみ」を並べ替え（↑↓キーでも動かせます）")

    handle.focus()
    page.keyboard.press("ArrowUp")

    assert names(page) == ["身だしなみ", "家のこと"]
    expect(handle).to_be_focused()
    expect(page.locator("#tabs [data-tab]").nth(1)).to_contain_text("身だしなみ")
