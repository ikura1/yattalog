"""デプロイのあと、開いたままの画面を新しいスクリプトに切り替える。"""

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def serve_grid_from_newer_build(page):
    """サーバーが新しい版に変わったことにする（一覧が、別のスクリプトの URL を返す）。"""

    def handle(route):
        response = route.fetch()
        body = response.text().replace('data-app-js="/static/js/app.js"', 'data-app-js="/static/js/app.NEW.js"')
        route.fulfill(response=response, body=body)

    page.route("**/grid/", handle)


def test_サーバーが新しい版になったら_開いたままの画面を読み込み直す(home):
    """古いスクリプトのまま新しい画面を受け取ると、動きが食い違う（「カテゴリなし」のタブが空になった）。"""
    page = home
    page.evaluate("window.__stale = true")  # 読み込み直すと消える目印
    serve_grid_from_newer_build(page)

    page.evaluate("document.dispatchEvent(new CustomEvent('yl:changed'))")  # 一覧の読み直しを起こす

    page.wait_for_function("() => window.__stale === undefined")
    expect(page.locator("#grid .tile", has_text="シーツ交換")).to_be_visible()


def test_読み込み直しても版が合わないときは_繰り返さない(home):
    page = home
    serve_grid_from_newer_build(page)
    page.evaluate("document.dispatchEvent(new CustomEvent('yl:changed'))")
    page.wait_for_load_state("load")
    page.wait_for_timeout(500)
    page.evaluate("window.__second = true")

    page.evaluate("document.dispatchEvent(new CustomEvent('yl:changed'))")
    page.wait_for_timeout(1200)

    assert page.evaluate("window.__second") is True  # 2回目は読み込み直していない


def test_シートを開いている間は_読み込み直さず_閉じてから行う(home):
    page = home
    page.evaluate("window.__stale = true")
    serve_grid_from_newer_build(page)
    page.get_by_role("button", name="メニュー").click()
    expect(page.locator("#sheet")).to_be_visible()

    page.evaluate("document.dispatchEvent(new CustomEvent('yl:changed'))")
    page.wait_for_timeout(800)
    assert page.evaluate("window.__stale") is True  # 開いている間は、そのまま

    page.keyboard.press("Escape")

    page.wait_for_function("() => window.__stale === undefined")
