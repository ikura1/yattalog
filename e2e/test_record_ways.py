"""段階で選ぶ・チェックする（決定 076）：押すとシートが開き、スライダーやチェックで記録する。"""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from playwright.sync_api import expect

from apps.events.models import Log
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.dates import today_in
from apps.events.services.logs import When
from e2e.pages import tile
from e2e.test_accessibility import violations
from e2e.test_number import shot

pytestmark = pytest.mark.e2e

ITEMS = ["床", "トイレ", "風呂", "キッチン"]


@pytest.fixture
def pain(logged_in_page, user):
    event = ev_svc.create_event(user, name="頭痛", emoji="🤕", color="grape", number_kind="scale")
    page = logged_in_page
    page.goto(page.base_url + "/")
    return page, event


@pytest.fixture
def clean(logged_in_page, user):
    event = ev_svc.create_event(user, name="掃除", emoji="🧹", color="teal", number_kind="check", check_items=ITEMS)
    page = logged_in_page
    page.goto(page.base_url + "/")
    return page, event


def the_tile(page, name):
    return page.locator("#grid .tile", has_text=name)


def saved(page):
    expect(page.locator(".toast:not(.hint)")).to_contain_text("記録しました")
    expect(page.locator("#sheet")).to_be_hidden()


def test_段階のイベントは_押すとスライダーが開き_選んで記録できる(pain):
    page, event = pain

    the_tile(page, "頭痛").click()
    slider = page.get_by_label("段階（1〜5）")
    expect(slider).to_have_value("3")
    expect(page.locator(".scale-now")).to_have_text("3")
    slider.focus()
    page.keyboard.press("ArrowRight")  # 矢印キーでも動く
    expect(page.locator(".scale-now")).to_have_text("4")
    page.get_by_role("button", name="やった！を記録").click()

    saved(page)
    assert [log.value for log in Log.objects.filter(event=event)] == [Decimal(4)]

    # 次に押すと、前回の段階に合わせてある
    the_tile(page, "頭痛").click()
    expect(page.get_by_label("段階（1〜5）")).to_have_value("4")


def test_段階のない記録の編集は_スライダーを動かすまで_段階を付けない(pain, user):
    page, event = pain
    log = log_svc.record(user, event.id, uuid.uuid4()).log

    page.goto(f"{page.base_url}/events/{event.id}/")
    page.locator(".logs").get_by_role("button", name="編集").click()
    keep = page.get_by_label("段階は付けない")
    expect(keep).to_be_checked()
    expect(page.locator(".scale-now")).to_have_text("—")
    page.get_by_label("メモ").fill("寝不足")
    page.get_by_role("button", name="保存する").click()
    expect(page.locator(".toast:not(.hint)")).to_contain_text("更新しました")
    log.refresh_from_db()
    assert (log.value, log.memo) == (None, "寝不足")

    page.locator(".logs").get_by_role("button", name="編集").click()
    page.get_by_label("段階（1〜5）").fill("5")
    expect(page.get_by_label("段階は付けない")).not_to_be_checked()
    expect(page.locator(".scale-now")).to_have_text("5")
    page.get_by_role("button", name="保存する").click()
    expect(page.locator(".logs .num")).to_have_text("5/5")
    log.refresh_from_db()
    assert log.value == Decimal(5)


def test_チェックのイベントは_押すと項目が開き_選んで記録できる(clean, user):
    page, event = clean

    the_tile(page, "掃除").click()
    for name in ("床", "風呂"):
        page.locator("#sheet-body .checks label", has_text=name).click()
    expect(page.get_by_label("床")).to_be_checked()
    page.get_by_role("button", name="やった！を記録").click()

    saved(page)
    assert [log.checks for log in Log.objects.filter(event=event)] == [["床", "風呂"]]

    # 次に押すと、前回と同じものに印が入っている。外して記録もできる
    the_tile(page, "掃除").click()
    expect(page.get_by_label("風呂")).to_be_checked()
    expect(page.get_by_label("トイレ")).not_to_be_checked()
    expect(page.locator("#sheet-body")).to_contain_text("前回と同じものに、印を入れてあります")


def test_イベントの編集で_チェックを選ぶと_項目の欄が出る(home):
    page = home
    tile(page).click(button="right")
    page.locator("#sheet-body").get_by_role("button", name="イベントを編集").click()
    items, unit = page.locator("#evItems"), page.locator("#evNumUnit")
    expect(items).to_be_hidden()

    page.locator("#sheet-body .seg label", has_text="チェックする").click()
    expect(items).to_be_visible()
    expect(unit).to_be_hidden()
    shot(page, "ways-event-form")
    items.fill("表\n裏")
    page.get_by_role("button", name="保存する").click()
    expect(page.locator(".toast:not(.hint)")).to_contain_text("保存しました")

    # 一覧が新しくなり、シートが閉じてから押す
    expect(page.locator("#grid [data-number-url]")).to_have_count(1)
    expect(page.locator("#evItems")).to_have_count(0)
    tile(page).click()
    expect(page.get_by_label("表")).to_be_visible()

    # 段階に変えると、どちらの欄も出ない
    page.keyboard.press("Escape")
    tile(page).click(button="right")
    page.locator("#sheet-body").get_by_role("button", name="イベントを編集").click()
    page.locator("#sheet-body .seg label", has_text="段階で選ぶ").click()
    expect(page.locator("#evItems")).to_be_hidden()
    expect(page.locator("#evNumUnit")).to_be_hidden()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_段階とチェックのシートと詳細に_axe_の指摘がない(pain, user, scheme):
    page, event = pain
    page.emulate_media(color_scheme=scheme)
    today = today_in(user.timezone)
    clean = ev_svc.create_event(user, name="掃除", emoji="🧹", color="teal", number_kind="check", check_items=ITEMS)
    for i in range(8):
        log_svc.record(user, event.id, uuid.uuid4(), When(date=today - timedelta(i + 1)), "", value=str(1 + i * 3 % 5))
        log_svc.record(user, clean.id, uuid.uuid4(), When(date=today - timedelta(i + 1)), "", checks=ITEMS[: i % 4])

    for e, name in ((event, "scale"), (clean, "check")):
        page.goto(f"{page.base_url}/events/{e.id}/")
        page.wait_for_load_state("networkidle")
        assert violations(page) == [], name
        shot(page, f"ways-{name}-detail-{scheme}")

    page.goto(page.base_url + "/")
    the_tile(page, "頭痛").click()
    page.get_by_label("段階（1〜5）").wait_for()
    assert violations(page) == [], "段階のシート"
    shot(page, f"ways-scale-sheet-{scheme}")
    page.keyboard.press("Escape")
    the_tile(page, "掃除").click()
    page.locator("#sheet-body .checks").wait_for()
    assert violations(page) == [], "チェックのシート"
    shot(page, f"ways-check-sheet-{scheme}")
