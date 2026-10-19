"""読み上げ・キーボード・色の見分けやすさを、axe で自動で確かめる（2026-10-15）。

ラベルの抜け、見出しや目印（main）の欠け、文字と背景のコントラスト不足などを、CI で毎回見つける。
"""

import uuid
from datetime import time, timedelta

import pytest
from axe_playwright_python.sync_playwright import Axe

from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.dates import today_in
from apps.events.services.logs import When

pytestmark = pytest.mark.e2e


@pytest.fixture
def busy(logged_in_page, user):
    """記録がある程度たまった状態（草・統計・履歴がすべて出る）。"""
    today = today_in(user.timezone)
    house = ev_svc.create_category(user, "家のこと", "🏠")
    event = ev_svc.create_event(user, name="家計簿", emoji="📒", color="sun", streak_unit="week", category_id=house.id)
    ev_svc.create_event(user, name="散髪", emoji="✂️", color="pink")
    for i in range(1, 200, 4):
        log_svc.record(user, event.id, uuid.uuid4(), When(date=today - timedelta(i), time=time(8)), "メモ")
    return logged_in_page, event


def violations(page) -> list[str]:
    # シートが開く動きの途中だと、色が薄く測られる。動きが終わってから検査する
    page.wait_for_function("() => document.getAnimations().every((a) => a.playState !== 'running')")
    result = Axe().run(page)
    return [f"{v['id']}（{v['impact']}）: {v['nodes'][0]['target']}" for v in result.response["violations"]]


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_ホーム_ふりかえり_イベント詳細に_axe_の指摘がない(busy, scheme):
    page, event = busy
    page.emulate_media(color_scheme=scheme)
    for url in ("/", "/review/", f"/events/{event.id}/"):
        page.goto(page.base_url + url)
        page.wait_for_load_state("networkidle")
        assert violations(page) == [], url

    # カテゴリの一覧と編集画面（シート）
    page.goto(page.base_url + "/")
    page.get_by_label("カテゴリを編集").click()
    page.locator("#sheet-body .catlist").wait_for()
    assert violations(page) == [], "カテゴリの一覧"
    page.locator(".cat-open").first.click()
    page.locator("#evName").wait_for()
    assert violations(page) == [], "カテゴリの編集"

    # 実績の一覧（シート）
    page.goto(page.base_url + "/")
    page.get_by_role("button", name="メニュー").click()
    page.get_by_role("button", name="実績", exact=False).first.click()
    page.locator("#sheet-body .ach").wait_for()
    assert violations(page) == [], "実績"
