"""規約とポリシーの改定の知らせ（決定 073）。"""

import pytest

from apps.accounts import notices
from apps.accounts.models import PRIVACY_VERSION, TERMS_VERSION

pytestmark = pytest.mark.django_db


def agreed(user, terms=TERMS_VERSION, privacy=PRIVACY_VERSION):
    user.terms_version, user.privacy_version = terms, privacy
    user.save(update_fields=["terms_version", "privacy_version"])
    return user


def test_登録したときの版が_いまと同じなら_知らせはない(user):
    assert notices.legal_notices(agreed(user)) == []


def test_ポリシーが改定されたら_名前と改定日と要点を知らせる(user, settings):
    settings.PRIVACY_REVISED = "2026年11月10日"
    settings.PRIVACY_CHANGE = "健康に関する記録の扱いを書き足しました"

    [notice] = notices.legal_notices(agreed(user, privacy="2026-10-17"))

    assert (notice.name, notice.url_name) == ("プライバシーポリシー", "web:privacy")
    assert (notice.revised, notice.summary) == ("2026年11月10日", "健康に関する記録の扱いを書き足しました")


def test_両方が改定されたら_規約_ポリシーの順に知らせる(user):
    found = notices.legal_notices(agreed(user, terms="2026-10-12", privacy="2026-10-13"))

    assert [n.name for n in found] == ["利用規約", "プライバシーポリシー"]


def test_閉じたら_もう知らせない(user):
    agreed(user, privacy="2026-10-17")

    notices.mark_legal_seen(user)

    user.refresh_from_db()
    assert notices.legal_notices(user) == []


def test_閉じても_登録のときに同意した版の記録は変えない(user):
    agreed(user, privacy="2026-10-17")

    notices.mark_legal_seen(user)

    user.refresh_from_db()
    assert user.privacy_version == "2026-10-17"


def test_閉じたあとに_また改定されたら_もう一度知らせる(user, monkeypatch):
    agreed(user, privacy="2026-10-17")
    notices.mark_legal_seen(user)

    monkeypatch.setattr(notices, "PRIVACY_VERSION", "2027-01-01")

    assert [n.name for n in notices.legal_notices(user)] == ["プライバシーポリシー"]


def test_同意の記録がない人には_知らせない(user):
    """管理用に作ったアカウントなど。登録の流れを通っていないので、比べる版がない。"""
    assert notices.legal_notices(agreed(user, terms="", privacy="")) == []
