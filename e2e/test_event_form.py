"""イベントの追加・編集シート（アイコンの入力欄、カテゴリの絵文字と選択）。"""

import pytest
from playwright.sync_api import expect

from apps.events.services import events as ev_svc

pytestmark = pytest.mark.e2e


def test_入力欄に絵文字を入れると_おすすめの選択が外れて_そのアイコンで追加される(home):
    page = home
    page.locator("#addTile").click()
    page.locator("#evName").fill("ぎょうざ")
    page.get_by_text("ほかの絵文字", exact=True).click()
    page.locator('.emojis .emo-opt:has(input[value="✂️"])').click()

    page.locator("#evEmoji").press_sequentially("🍜🥟")  # 続けて打ったら、最後の1つだけ残る
    expect(page.locator("#evEmoji")).to_have_value("🥟")
    expect(page.locator('input[name="emoji"]:checked')).to_have_count(0)

    page.get_by_role("button", name="追加する").click()
    expect(page.locator("#grid .tile", has_text="ぎょうざ").locator(".emo")).to_have_text("🥟")


def test_おすすめを選び直すと_入力欄は空になる(home):
    page = home
    page.locator("#addTile").click()
    page.get_by_text("ほかの絵文字", exact=True).click()
    page.locator("#evEmoji").press_sequentially("🥟")

    page.locator('.emojis .emo-opt:has(input[value="✂️"])').click()

    expect(page.locator("#evEmoji")).to_have_value("")
    expect(page.locator('input[name="emoji"]:checked')).to_have_value("✂️")


def test_名前を入れると_合いそうな絵文字が選ばれて_そのアイコンで追加される(home):
    page = home
    page.locator("#addTile").click()
    page.locator("#evName").fill("排水口の掃除")

    expect(page.locator('.emo-row input[name="emoji"]:checked')).to_have_value("🕳️")
    expect(page.locator(".emo-why")).to_contain_text("合いそうなもの")
    page.get_by_role("button", name="追加する").click()

    expect(page.locator("#grid .tile", has_text="排水口の掃除").locator(".emo")).to_have_text("🕳️")


def test_自分で候補を選んだら_名前を変えても選び直さない(home):
    page = home
    page.locator("#addTile").click()
    page.locator("#evName").fill("シーツ交換")
    page.locator('.emo-row .emo-opt:has(input[value="☀️"])').click()

    page.locator("#evName").fill("シーツと布団")

    expect(page.locator('input[name="emoji"]:checked')).to_have_value("☀️")


def test_カテゴリを絵文字つきで追加すると_タブに絵文字が出る(home):
    page = home
    page.locator(".tab-add").click()
    page.get_by_role("button", name="＋ カテゴリを追加").click()
    page.locator("#evName").fill("家事")
    expect(page.locator('.emo-row input[name="emoji"]:checked')).to_have_value("")  # カテゴリの絵文字は「なし」から
    page.get_by_text("ほかの絵文字", exact=True).click()
    page.locator("#evEmoji").press_sequentially("🧺🧹")  # 続けて打ったら、最後の1つだけ残る
    expect(page.locator("#evEmoji")).to_have_value("🧹")

    page.get_by_role("button", name="追加する").click()

    expect(page.locator("#toast-root")).to_contain_text("追加しました")
    expect(page.locator('#tabs [role="tab"]', has_text="家事").locator(".cat-emo")).to_have_text("🧹")


def test_カテゴリの削除は_アプリの中で確かめてから消す(home, user):
    from apps.events.services import events as ev_svc

    ev_svc.create_category(user, "家事")
    page = home
    page.reload()
    page.locator(".tab-add").click()
    page.locator(".cat-open", has_text="家事").click()
    page.get_by_role("button", name="このカテゴリを削除").click()
    expect(page.locator("#sheet-body")).to_contain_text("「家事」を削除しますか")

    page.get_by_role("button", name="削除する").click()

    expect(page.locator("#toast-root")).to_contain_text("削除しました")
    expect(page.locator('#tabs [role="tab"]', has_text="家事")).to_have_count(0)


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


def test_シートから追加すると_追加しましたと知らせが出る(home):
    """シートからの操作のあとの知らせが、出ていなかったことがある（合図の順番の問題）。"""
    page = home
    page.locator("#addTile").click()
    page.locator("#evName").fill("歯医者")

    page.get_by_role("button", name="追加する").click()

    expect(page.locator(".toast:not(.hint)")).to_contain_text("追加しました")
    expect(page.locator("#sheet")).to_be_hidden()
    expect(page.locator("#grid .tile", has_text="歯医者")).to_be_visible()
