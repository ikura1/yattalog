"""規約とポリシーの改定の知らせ（決定 073）。

登録のときに同意した版（`terms_version`・`privacy_version`）と、いまの版を比べる。
知らせを閉じたら、その版を「見た」として別に覚える（同意の記録は変えない）。
"""

from dataclasses import dataclass

from django.conf import settings

from apps.accounts.models import PRIVACY_VERSION, TERMS_VERSION


@dataclass(frozen=True)
class LegalNotice:
    name: str
    url_name: str
    revised: str  # 改定日（画面に出す形）
    summary: str  # 何が変わったか。なければ空


def legal_notices(user) -> list[LegalNotice]:
    """まだ知らせていない改定。規約、ポリシーの順。同意の記録がない人には出さない。"""
    documents = [
        ("利用規約", "web:terms", TERMS_VERSION, user.terms_seen or user.terms_version, "TERMS"),
        ("プライバシーポリシー", "web:privacy", PRIVACY_VERSION, user.privacy_seen or user.privacy_version, "PRIVACY"),
    ]
    return [
        LegalNotice(name, url_name, getattr(settings, f"{key}_REVISED"), getattr(settings, f"{key}_CHANGE"))
        for name, url_name, current, known, key in documents
        if known and known != current
    ]


def mark_legal_seen(user) -> None:
    """いまの版を、知らせた版として覚える。"""
    user.terms_seen, user.privacy_seen = TERMS_VERSION, PRIVACY_VERSION
    user.save(update_fields=["terms_seen", "privacy_seen"])
