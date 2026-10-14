"""ホームでの1タップ記録（決定 028：楽観的更新と取り消し）と、上限に達したときの知らせ。"""

import re

import pytest
from playwright.sync_api import expect

from apps.events.models import Log
from e2e.pages import tile

pytestmark = pytest.mark.e2e


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


def test_操作が多すぎると言われたら_その旨を知らせてタイルを元に戻す(home):
    page = home
    page.route(
        "**/record/", lambda route: route.fulfill(status=429, body="操作が多すぎます", headers={"Retry-After": "30"})
    )

    tile(page).click()

    expect(page.locator(".toast:not(.hint)")).to_contain_text("操作が多すぎます")
    expect(tile(page).locator(".ago")).to_have_text("まだ")


def test_取り消しの知らせが消えたあとでも_長押しシートから_さっきの記録を取り消せる(home):
    page = home
    tile(page).click()
    expect(page.locator(".toast:not(.hint)")).to_contain_text("シーツ交換 を記録しました")
    expect(page.locator(".toast:not(.hint)")).to_have_count(0, timeout=12000)  # 取り消しのボタンが消える（7秒）のを待つ

    tile(page).click(button="right")  # 長押しと同じシートが開く
    page.get_by_role("button", name="さっきの記録を取り消す").click()

    expect(page.locator(".toast:not(.hint)")).to_contain_text("取り消しました")
    expect(tile(page).locator(".ago")).to_have_text("まだ")
    assert Log.objects.count() == 0


# --- 記録した直後の知らせから、次の操作へ（決定 055） ---


def test_記録した直後の知らせから_取り消し_メモ_シェア_詳細へ行ける(home):
    page = home
    tile(page).click()

    toast = page.locator(".toast:not(.hint)")
    expect(toast).to_contain_text("シーツ交換 を記録しました")
    expect(toast.get_by_role("button")).to_have_text(["取り消す", "メモ", "シェア", "詳細"])


def test_知らせの_詳細_を押すと_イベントの詳細が開く(home):
    page = home
    tile(page).click()

    page.locator(".toast:not(.hint)").get_by_role("button", name="詳細").click()

    expect(page.get_by_role("heading", name="シーツ交換")).to_be_visible()
    expect(page.locator(".stat", has_text="記録回数").locator(".v")).to_have_text("1回")


def test_知らせの_シェア_を押すと_その記録のシェアが開く(home):
    page = home
    tile(page).click()

    page.locator(".toast:not(.hint)").get_by_role("button", name="シェア").click()

    expect(page.locator("#sheet")).to_contain_text("#Yattalog")
    expect(page.locator("#shareCard")).to_have_attribute("data-headline", "はじめての記録")


def test_記録すると_手ごたえがある_震えと_タイルの印(home):
    page = home
    page.add_init_script(
        "navigator.vibrate = (ms) => { (window.__vibrated = window.__vibrated || []).push(ms); return true; };"
    )
    page.reload()

    tile(page).click()

    expect(tile(page)).to_have_class(re.compile(r"\bstamp\b"))
    assert page.evaluate("window.__vibrated") == [12]
