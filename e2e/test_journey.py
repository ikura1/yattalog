"""はじめての人が、登録してから退会するまでの通し（β を開く前の確認の、自動でできる部分）。

Google ログインそのものは、ここでは通らない（`apps/accounts/tests/test_google_login.py` で確かめる）。
"""

import csv
import io
import re
import zipfile

import pytest
from playwright.sync_api import expect

from apps.accounts.models import User
from apps.events.models import Category, Event, Log
from apps.spaces.models import Space

pytestmark = pytest.mark.e2e


def test_テンプレートで始めて_記録し_詳細を見て_書き出して_退会する(logged_in_page, user):
    page = logged_in_page
    page.goto(page.base_url + "/")

    # 1. はじめての画面：テンプレートを2つ選んで追加する
    expect(page.locator("#welcome")).to_be_visible()
    page.locator(".starter", has_text="シーツ交換").click()
    page.locator(".starter", has_text="散髪").click()
    page.locator("#welcome").get_by_role("button", name="追加する").click()
    expect(page.locator("#grid .tile .name")).to_have_text(["シーツ交換", "散髪"])
    expect(page.get_by_role("tab", name="家事")).to_be_visible()

    # 2. タップで記録する。サーバーが書き終わるのを、成功のトーストで待つ
    sheets = page.locator("#grid .tile", has_text="シーツ交換")
    sheets.click()
    expect(sheets.locator(".ago")).to_have_text("さっき")
    expect(page.locator(".toast:not(.hint)")).to_contain_text("シーツ交換 を記録しました")

    # 3. 編集モードからイベントの詳細を開く。記録が1回になっている
    page.get_by_role("button", name="編集").click()
    sheets.click(force=True)  # 編集モードのタイルは揺れているので、止まるのを待たずに押す
    expect(page.get_by_role("heading", name="シーツ交換")).to_be_visible()
    expect(page.locator(".stat", has_text="記録回数").locator(".v")).to_have_text("1回")
    page.get_by_role("link", name="ホームに戻る").click()
    expect(page.locator("#grid .tile", has_text="散髪")).to_be_visible()

    # 4. データを書き出す。ZIP に、イベントと、いまの記録が入っている
    page.get_by_role("button", name="メニュー").click()
    with page.expect_download() as download:
        page.get_by_role("button", name="データを書き出す").click()
    assert re.fullmatch(r"yattalog-\d{8}\.zip", download.value.suggested_filename)
    with zipfile.ZipFile(download.value.path()) as z:
        events = list(csv.reader(io.StringIO(z.read("events.csv").decode("utf-8-sig"))))
        logs = list(csv.reader(io.StringIO(z.read("logs.csv").decode("utf-8-sig"))))
    assert [row[0] for row in events[1:]] == ["シーツ交換", "散髪"]
    assert [(row[0], row[1]) for row in logs[1:]] == [("シーツ交換", "家事")]

    # 5. 退会する。ログイン画面に戻り、データが何も残っていない
    page.get_by_role("button", name="退会する").click()
    page.get_by_label("すべてのデータが削除され、元に戻せないことを理解しました").check()
    page.get_by_role("button", name="退会してデータを削除する").click()
    expect(page.locator(".messages")).to_contain_text("退会しました")
    expect(page.get_by_role("button", name="Google でログイン").first).to_be_visible()
    counts = [m.objects.count() for m in (User, Space, Category, Event, Log)]
    assert counts == [0, 0, 0, 0, 0]

    # 6. 退会したあとは、ホームを開いてもログイン画面に送られる
    page.goto(page.base_url + "/")
    expect(page.get_by_role("button", name="Google でログイン").first).to_be_visible()
