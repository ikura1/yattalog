"""ホーム画面への追加（PWA）の案内（決定 043）。"""

import pytest
from playwright.sync_api import expect

from apps.events.services import events as ev_svc

pytestmark = pytest.mark.e2e


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
