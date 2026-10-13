"""イベントの追加・編集シート（アイコンの入力欄、カテゴリの絵文字と選択）。"""

import pytest
from playwright.sync_api import expect

from apps.events.services import events as ev_svc

pytestmark = pytest.mark.e2e


def test_入力欄に絵文字を入れると_おすすめの選択が外れて_そのアイコンで追加される(home):
    page = home
    page.locator("#addTile").click()
    page.locator("#evName").fill("ぎょうざ")
    page.locator('.emo-opt:has(input[value="✂️"])').click()

    page.locator("#evEmoji").press_sequentially("🍜🥟")  # 続けて打ったら、最後の1つだけ残る
    expect(page.locator("#evEmoji")).to_have_value("🥟")
    expect(page.locator('input[name="emoji"]:checked')).to_have_count(0)

    page.get_by_role("button", name="追加する").click()
    expect(page.locator("#grid .tile", has_text="ぎょうざ").locator(".emo")).to_have_text("🥟")


def test_おすすめを選び直すと_入力欄は空になる(home):
    page = home
    page.locator("#addTile").click()
    page.locator("#evEmoji").press_sequentially("🥟")

    page.locator('.emo-opt:has(input[value="✂️"])').click()

    expect(page.locator("#evEmoji")).to_have_value("")
    expect(page.locator('input[name="emoji"]:checked')).to_have_value("✂️")


def test_カテゴリを絵文字つきで追加すると_タブに絵文字が出る(home):
    page = home
    page.locator(".tab-add").click()
    new = page.locator(".inline-new")
    new.locator('input[name="emoji"]').press_sequentially("🧺🧹")  # 続けて打ったら、最後の1つだけ残る
    expect(new.locator('input[name="emoji"]')).to_have_value("🧹")
    new.locator('input[name="name"]').fill("家事")

    new.get_by_role("button", name="追加").click()

    expect(page.locator('#tabs [role="tab"]', has_text="家事").locator(".cat-emo")).to_have_text("🧹")


@pytest.mark.parametrize("opener", [".tab-add", "#grid .tile.add"])
def test_シートを開いても入力欄にフォーカスせず_キーボードが出ない(home, opener):
    page = home
    page.locator(opener).click()
    expect(page.locator("#sheet")).to_be_visible()
    expect(page.locator("#sheet")).to_be_focused()  # 読み上げのため、フォーカスはシートに移す

    assert page.evaluate("document.activeElement.matches('input, textarea')") is False


def test_カテゴリのタブで追加を押すと_そのカテゴリが選ばれた状態で開く(home, user):
    house = ev_svc.create_category(user, "家事")
    page = home
    page.reload()
    page.locator('#tabs [role="tab"]', has_text="家事").click()

    page.locator("#grid .tile.add").click()

    expect(page.locator(f'#sheet input[name="category"][value="{house.id}"]')).to_be_checked()


def test_すべてのタブで追加を押すと_カテゴリはなしのまま開く(home, user):
    ev_svc.create_category(user, "家事")
    page = home
    page.reload()
    page.locator('#tabs [role="tab"]', has_text="家事").click()
    page.locator('#tabs [role="tab"]', has_text="すべて").click()

    page.locator("#grid .tile.add").click()

    expect(page.locator('#sheet input[name="category"][value=""]')).to_be_checked()


def test_フォームのカテゴリは_絵文字があってもなくても同じ高さの1行で並ぶ(home, user):
    ev_svc.create_category(user, "家事", emoji="🧹")
    ev_svc.create_category(user, "買い物")
    page = home
    page.reload()
    page.locator("#grid .tile.add").click()

    expect(page.locator("#sheet .chips")).to_be_visible()
    # シートは下から滑って出てくるので、2つは同じ瞬間に測る
    with_emoji, without = page.locator("#sheet .chips label").evaluate_all(
        """ls => ["家事", "買い物"]
              .map(t => ls.find(l => l.textContent.includes(t)).querySelector(":scope > span"))
              .map(s => s.getBoundingClientRect())
              .map(r => ({ top: r.top, height: r.height }))"""
    )
    assert with_emoji == without
