"""イベント詳細の「よくやる」（時期・曜日・時間帯・日にちの切り替え、決定 060）。"""

import uuid
from datetime import time, timedelta

import pytest
from playwright.sync_api import expect

from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.dates import today_in
from apps.events.services.logs import When

pytestmark = pytest.mark.e2e


def test_よくやるの切り替えで_曜日を見られて_開き直しても覚えている(logged_in_page, user):
    event = ev_svc.create_event(user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week")
    today = today_in(user.timezone)
    for days in (0, 7, 14):
        log_svc.record(user, event.id, uuid.uuid4(), When(date=today - timedelta(days)))
    page = logged_in_page
    page.goto(page.base_url + f"/events/{event.id}/")

    season = page.get_by_role("tabpanel", name="時期")
    expect(season).to_be_visible()
    page.get_by_role("tab", name="曜日").click()

    weekday = page.get_by_role("tabpanel", name="曜日")
    expect(weekday).to_be_visible()
    expect(weekday).to_contain_text("よくやるのは")
    expect(season).to_be_hidden()
    expect(page.get_by_role("tab", name="曜日")).to_have_attribute("aria-selected", "true")

    page.reload()
    expect(page.get_by_role("tabpanel", name="曜日")).to_be_visible()


def test_幅の狭い画面でも_詳細は横にはみ出さない(logged_in_page, user):
    """記録の履歴の「削除」ボタンが、320px で右にはみ出していた。"""
    event = ev_svc.create_event(user, name="家計簿", emoji="📒", color="sun", streak_unit="month")
    log_svc.record(
        user, event.id, uuid.uuid4(), When(date=today_in(user.timezone) - timedelta(400), time=time(8)), "冬用に替えた"
    )
    page = logged_in_page
    page.set_viewport_size({"width": 320, "height": 800})
    page.goto(page.base_url + f"/events/{event.id}/")
    expect(page.get_by_role("button", name="この記録を削除")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth - innerWidth") == 0
