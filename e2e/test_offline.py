"""オフラインのときの案内（Service Worker、決定 049）。"""

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_つながらないときは_オフラインの案内が出て_つながったら戻れる(home):
    page = home
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")  # Service Worker の準備ができるまで待つ
    page.wait_for_function("navigator.serviceWorker.controller !== null")

    page.context.set_offline(True)
    page.goto(page.base_url + "/")

    expect(page.get_by_role("heading", name="オフラインです")).to_be_visible()
    expect(page.locator("#grid")).to_have_count(0)

    page.context.set_offline(False)
    page.get_by_role("link", name="もう一度開く").click()

    expect(page.locator("#grid .tile", has_text="シーツ交換")).to_be_visible()


def test_Service_Worker_は_ログインした人の画面をしまわない(home):
    page = home
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    page.wait_for_function("navigator.serviceWorker.controller !== null")
    page.reload()
    expect(page.locator("#grid .tile", has_text="シーツ交換")).to_be_visible()

    cached = page.evaluate(
        """async () => {
            const urls = [];
            for (const name of await caches.keys()) {
                for (const request of await (await caches.open(name)).keys()) urls.push(new URL(request.url).pathname);
            }
            return urls;
        }"""
    )

    assert "/offline/" in cached
    assert all(path == "/offline/" or path.startswith("/static/") for path in cached), cached
