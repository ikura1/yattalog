"""シェア（画像を端末で作る、決定 053）。"""

import pytest
from playwright.sync_api import expect

from apps.events.services import events as ev_svc

pytestmark = pytest.mark.e2e


@pytest.fixture
def detail_with_log(logged_in_page, user):
    import uuid

    from apps.events.services import logs as log_svc

    event = ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week")
    log_svc.record(user, event.id, uuid.uuid4(), memo="冬用に替えた")
    page = logged_in_page
    page.goto(page.base_url + f"/events/{event.id}/")
    return page


def image_size(page):
    page.wait_for_function("() => { const i = document.querySelector('#shareImg'); return i && i.naturalWidth > 0; }")
    return page.evaluate(
        "() => { const i = document.querySelector('#shareImg'); return [i.naturalWidth, i.naturalHeight]; }"
    )


def test_詳細からシェアを開くと_1080x1350_の画像ができる(detail_with_log):
    page = detail_with_log
    page.locator(".row").get_by_role("button", name="シェア").first.click()

    assert image_size(page) == [1080, 1350]
    expect(page.locator("#sheet")).to_contain_text("#Yattalog")


def test_メモを載せるにチェックすると_画像が作り直される(detail_with_log):
    page = detail_with_log
    page.locator(".row").get_by_role("button", name="シェア").first.click()
    image_size(page)
    before = page.locator("#shareImg").get_attribute("src")

    page.get_by_label("メモも載せる").check()

    page.wait_for_function("(old) => document.querySelector('#shareImg').src !== old", arg=before)
    assert image_size(page) == [1080, 1350]


def test_共有シートが使えない環境では_画像を保存できる(detail_with_log):
    page = detail_with_log
    page.locator(".row").get_by_role("button", name="シェア").first.click()
    image_size(page)
    expect(page.locator("#shareSave")).to_be_hidden()

    page.get_by_role("button", name="共有する").click()

    expect(page.locator("#shareNote")).to_contain_text("画像を保存する")
    with page.expect_download() as download:
        page.locator("#shareSave").click()
    assert download.value.suggested_filename == "yattalog.png"
