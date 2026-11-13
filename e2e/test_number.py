"""数字の記録（決定 074）：数字を聞くイベントは、押すと数字のシートが開く。"""

import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from playwright.sync_api import expect

from apps.events.models import Log
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.dates import today_in
from apps.events.services.logs import When
from e2e.pages import tile
from e2e.test_accessibility import violations

pytestmark = pytest.mark.e2e

SHOTS = Path("e2e-shots")


def shot(page, name):
    if SHOTS.is_dir():  # 見た目を確かめたいときだけ、手元でフォルダを作る
        page.screenshot(path=SHOTS / f"{name}.png", full_page=True)


@pytest.fixture
def run(logged_in_page, user):
    event = ev_svc.create_event(user, name="ランニング", emoji="🏃", color="sky", number_kind="sum", number_unit="km")
    page = logged_in_page
    page.goto(page.base_url + "/")
    return page, event


def number_tile(page):
    return page.locator("#grid .tile", has_text="ランニング")


def test_数字を聞くイベントは_押すとシートが開き_数字を入れて記録できる(run):
    page, event = run

    number_tile(page).click()
    value = page.get_by_label("数字（km）")
    value.fill("5.2")
    page.get_by_role("button", name="やった！を記録").click()

    expect(page.locator(".toast:not(.hint)")).to_contain_text("記録しました")
    expect(number_tile(page).locator(".ago")).to_have_text("さっき")
    assert [log.value for log in Log.objects.filter(event=event)] == [Decimal("5.2")]

    # 次に押すと、前回の数字が入っている。触ると丸ごと選ばれ、打てば置き換わる
    number_tile(page).click()
    value = page.get_by_label("数字（km）")
    expect(value).to_have_value("5.2")
    value.focus()
    page.keyboard.type("3")
    expect(value).to_have_value("3")


def test_数字を空にしても_記録できる(run):
    page, event = run

    number_tile(page).click()
    page.get_by_label("数字（km）").wait_for()
    page.get_by_role("button", name="やった！を記録").click()

    expect(page.locator(".toast:not(.hint)")).to_contain_text("記録しました")
    assert [log.value for log in Log.objects.filter(event=event)] == [None]


def test_数字ではないものを入れると_シートに誤りが出て_記録されない(run):
    page, event = run

    number_tile(page).click()
    page.get_by_label("数字（km）").fill("たくさん")
    page.get_by_role("button", name="やった！を記録").click()

    expect(page.locator("#sheet-body")).to_contain_text("数字は 0〜999,999,999 の範囲で入れてください")
    assert Log.objects.filter(event=event).count() == 0


def test_数字を聞かないイベントは_今までどおり1タップで記録する(home):
    page = home

    tile(page).click()

    expect(page.locator(".toast:not(.hint)")).to_contain_text("シーツ交換 を記録しました")
    expect(page.locator("#sheet")).to_be_hidden()


def test_イベントの編集で_数字の記録を選ぶと_単位の欄が出る(home):
    page = home
    tile(page).click(button="right")
    page.locator("#sheet-body").get_by_role("link", name="編集").or_(
        page.locator("#sheet-body").get_by_role("button", name="編集")
    ).first.click()
    unit = page.locator("#evNumUnit")
    expect(unit).to_be_hidden()

    page.locator("#sheet-body label", has_text="推移を見る").click()

    expect(unit).to_be_visible()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_数字のシートと_合計_推移の詳細に_axe_の指摘がない(run, user, scheme):
    page, event = run
    page.emulate_media(color_scheme=scheme)
    today = today_in(user.timezone)
    weight = ev_svc.create_event(user, name="体重", emoji="⚖️", color="pink", number_kind="trend", number_unit="kg")
    for i in range(12):
        log_svc.record(user, event.id, uuid.uuid4(), When(date=today - timedelta(i * 9)), "", value=str(3 + i % 4))
        log_svc.record(user, weight.id, uuid.uuid4(), When(date=today - timedelta(i)), "", value=f"62.{(i * 7) % 10}")

    for e, name in ((event, "sum"), (weight, "trend")):
        page.goto(f"{page.base_url}/events/{e.id}/")
        page.wait_for_load_state("networkidle")
        assert violations(page) == [], name
        shot(page, f"number-{name}-{scheme}")

    page.goto(page.base_url + "/")
    number_tile(page).click()
    page.get_by_label("数字（km）").wait_for()
    assert violations(page) == [], "数字のシート"
    shot(page, f"number-sheet-{scheme}")
