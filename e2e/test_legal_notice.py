"""規約とポリシーの改定の知らせ（決定 073）。閉じると消え、開き直しても戻らない。"""

from pathlib import Path

import pytest
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect

from apps.accounts.models import TERMS_VERSION

pytestmark = pytest.mark.e2e

SHOTS = Path(__file__).parent.parent / "test-results"


@pytest.fixture
def outdated(user):
    """ポリシーが改定される前に登録した人。"""
    user.terms_version, user.privacy_version = TERMS_VERSION, "2026-10-17"
    user.save(update_fields=["terms_version", "privacy_version"])
    return user


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_改定の知らせは_閉じると消えて_開き直しても戻らない(outdated, home, scheme):
    page = home
    page.emulate_media(color_scheme=scheme)
    banner = page.locator("#legalBanner")
    expect(banner).to_contain_text("プライバシーポリシーを改定しました")
    expect(banner.get_by_role("link", name="プライバシーポリシー")).to_have_attribute("href", "/privacy/")
    SHOTS.mkdir(exist_ok=True)
    page.screenshot(path=SHOTS / f"legal-notice-{scheme}.png")
    found = Axe().run(page, context="#legalBanner").response["violations"]
    assert [v["id"] for v in found] == []

    banner.get_by_role("button", name="この知らせを閉じる").click()

    expect(banner).to_have_count(0)
    page.reload()
    expect(page.locator("#grid")).to_be_visible()
    expect(page.locator("#legalBanner")).to_have_count(0)
    outdated.refresh_from_db()
    assert outdated.privacy_version == "2026-10-17"  # 同意の記録は変えない
