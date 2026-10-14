"""ふりかえり（1年の草、決定 058）。"""

import uuid
from datetime import timedelta

import pytest
from playwright.sync_api import expect

from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.dates import today_in
from apps.events.services.logs import When

pytestmark = pytest.mark.e2e


def test_メニューからふりかえりを開き_マスを押すとその日にやったことが出る(home, user):
    sheets = ev_svc.list_events(user).get()
    water = ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf")
    day = today_in(user.timezone) - timedelta(3)
    log_svc.record(user, water.id, uuid.uuid4(), When(date=day))
    log_svc.record(user, sheets.id, uuid.uuid4())
    page = home

    page.get_by_role("button", name="メニュー").click()
    page.get_by_role("link", name="ふりかえり").click()

    expect(page.get_by_role("heading", name="ふりかえり")).to_be_visible()
    expect(page.locator("#reviewSum")).to_contain_text("2 回、2 日やった")
    expect(page.locator("#reviewDay")).to_contain_text("シーツ交換")

    # 1年分（53週）を並べるので、去年の同じ日付もある。曜日と回数まで含めて、その日のマスを選ぶ
    page.get_by_label(f"{day.month}月{day.day}日（{'月火水木金土日'[day.weekday()]}）：1回", exact=True).click()
    expect(page.locator("#reviewDay")).to_contain_text("水やり")
    expect(page.locator("#reviewDay")).not_to_contain_text("シーツ交換")

    page.get_by_role("link", name="シーツ交換").first.click()
    expect(page.locator("#reviewSum")).to_contain_text("1 回、1 日やった")
    expect(page).to_have_url(f"{page.base_url}/review/?event={sheets.id}&day={day.isoformat()}")
