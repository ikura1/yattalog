"""ホームでの1タップ記録（決定 028：楽観的更新と取り消し）。"""

import re

import pytest
from playwright.sync_api import expect

from apps.events.models import Log
from apps.events.services import events as ev_svc

pytestmark = pytest.mark.e2e


@pytest.fixture
def home(logged_in_page, user):
    ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week")
    page = logged_in_page
    page.goto(page.base_url + "/")
    return page


def tile(page):
    return page.locator("#grid .tile", has_text="シーツ交換")


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


# --- アイコンの入力欄（決定 035） ---


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


# --- カテゴリの絵文字（決定 036） ---


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


# --- レート制限（決定 037） ---


def test_操作が多すぎると言われたら_その旨を知らせてタイルを元に戻す(home):
    page = home
    page.route(
        "**/record/", lambda route: route.fulfill(status=429, body="操作が多すぎます", headers={"Retry-After": "30"})
    )

    tile(page).click()

    expect(page.locator(".toast:not(.hint)")).to_contain_text("操作が多すぎます")
    expect(tile(page).locator(".ago")).to_have_text("まだ")


# --- データの書き出し（決定 039） ---


def test_メニューから書き出すと_ZIP_がダウンロードされる(home):
    import zipfile

    page = home
    page.get_by_role("button", name="メニュー").click()
    with page.expect_download() as download:
        page.get_by_role("button", name="データを書き出す").click()

    assert re.fullmatch(r"yattalog-\d{8}\.zip", download.value.suggested_filename)
    with zipfile.ZipFile(download.value.path()) as z:
        assert "シーツ交換" in z.read("events.csv").decode("utf-8")


# --- 退会（決定 040） ---


def test_メニューから退会すると_ログイン画面に戻り_データが消えている(home):
    from apps.accounts.models import User
    from apps.events.models import Event

    page = home
    page.get_by_role("button", name="メニュー").click()
    page.get_by_role("button", name="退会する").click()
    page.get_by_label("すべてのデータが削除され、元に戻せないことを理解しました").check()

    page.get_by_role("button", name="退会してデータを削除する").click()

    expect(page.locator(".messages")).to_contain_text("退会しました")
    expect(page.get_by_role("button", name="Google でログイン")).to_be_visible()
    assert not User.objects.exists() and not Event.objects.exists()


# --- はじめて使うとき：テンプレート（決定 042） ---


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


# --- ホーム画面への追加（PWA）の案内（決定 043） ---

IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
)


@pytest.fixture
def iphone_home(browser, live_server, transactional_db, user):
    """iPhone の Safari として開いたホーム。"""
    from django.conf import settings
    from django.test import Client

    ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky")
    client = Client()
    client.force_login(user)
    context = browser.new_context(user_agent=IPHONE, viewport={"width": 390, "height": 760})
    cookie = client.cookies[settings.SESSION_COOKIE_NAME].value
    context.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": cookie, "url": live_server.url}])
    page = context.new_page()
    page.goto(live_server.url + "/")
    yield page
    context.close()


def test_iPhone_では_追加の案内が出て_手順を開ける(iphone_home):
    page = iphone_home
    expect(page.locator("#installBanner")).to_be_visible()

    page.locator("#installYes").click()

    expect(page.locator("#sheet")).to_contain_text("共有ボタン")
    expect(page.locator("#sheet")).not_to_contain_text("Android")


def test_案内を閉じると_開き直しても出ない(iphone_home):
    page = iphone_home
    page.locator("#installNo").click()
    expect(page.locator("#installBanner")).to_be_hidden()

    page.reload()

    expect(page.locator("#grid .tile", has_text="シーツ交換")).to_be_visible()
    expect(page.locator("#installBanner")).to_be_hidden()


def test_閉じてから7日たつと_また出る_3回閉じたら_もう出ない(iphone_home):
    page = iphone_home
    week_ago = "Date.now() - 8 * 24 * 60 * 60 * 1000"
    page.evaluate(f"localStorage.setItem('yl:install', JSON.stringify({{count: 2, until: {week_ago}}}))")
    page.reload()
    expect(page.locator("#installBanner")).to_be_visible()

    page.locator("#installNo").click()
    page.evaluate(f"localStorage.setItem('yl:install', JSON.stringify({{count: 3, until: {week_ago}}}))")
    page.reload()

    expect(page.locator("#grid .tile", has_text="シーツ交換")).to_be_visible()
    expect(page.locator("#installBanner")).to_be_hidden()


def test_パソコンなどでは_ブラウザが追加できると知らせてきたときだけ_案内が出る(home):
    page = home
    expect(page.locator("#installBanner")).to_be_hidden()

    page.evaluate("window.dispatchEvent(new Event('beforeinstallprompt'))")

    expect(page.locator("#installBanner")).to_be_visible()


def test_メニューから_追加の方法を開ける(home):
    page = home
    page.get_by_role("button", name="メニュー").click()
    page.get_by_role("button", name="ホーム画面に追加する方法").click()

    expect(page.locator("#sheet")).to_contain_text("iPhone・iPad")
    page.locator("#sheet [data-close-sheet]").click()
    expect(page.locator("#sheet")).to_be_hidden()
