"""データの書き出しと、退会。"""

import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_メニューから書き出すと_ZIP_がダウンロードされる(home):
    import zipfile

    page = home
    page.get_by_role("button", name="メニュー").click()
    with page.expect_download() as download:
        page.get_by_role("button", name="データを書き出す").click()

    assert re.fullmatch(r"yattalog-\d{8}\.zip", download.value.suggested_filename)
    with zipfile.ZipFile(download.value.path()) as z:
        assert "シーツ交換" in z.read("events.csv").decode("utf-8")


def test_メニューから退会すると_ログイン画面に戻り_データが消えている(home):
    from apps.accounts.models import User
    from apps.events.models import Event

    page = home
    page.get_by_role("button", name="メニュー").click()
    page.get_by_role("button", name="退会する").click()
    page.get_by_label("すべてのデータが削除され、元に戻せないことを理解しました").check()

    page.get_by_role("button", name="退会してデータを削除する").click()

    expect(page.locator(".messages")).to_contain_text("退会しました")
    expect(page.get_by_role("button", name="Google でログイン").first).to_be_visible()
    assert not User.objects.exists() and not Event.objects.exists()


def test_ログアウトは_押した瞬間に文言が変わる(home):
    page = home
    page.get_by_role("button", name="メニュー").click()
    # 送信だけ止めて、押した直後の表示を見る（アプリの処理は先に登録されているので、先に動く）
    page.evaluate("document.addEventListener('submit', (e) => e.preventDefault())")
    page.get_by_role("button", name="ログアウト").click()
    expect(page.locator("#sheet-body form[data-busy] button")).to_have_text("ログアウトしています…")
