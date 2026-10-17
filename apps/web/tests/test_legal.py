"""利用規約・プライバシーポリシー・問い合わせ先（SPEC 6章、決定 041）。"""

import pytest
from django.test import override_settings

FORM = "https://forms.example.com/yattalog-contact"
ISSUES = "https://github.com/ikura1/yattalog/issues"


@pytest.mark.parametrize("path,title", [("/terms/", "利用規約"), ("/privacy/", "プライバシーポリシー")])
def test_規約とポリシーは_ログインしなくても読める(client, db, path, title):
    r = client.get(path)
    assert r.status_code == 200 and title in r.content.decode()


@pytest.mark.parametrize("path", ["/terms/", "/privacy/"])
def test_空欄や下書きの印が残っていない(client, db, path):
    body = client.get(path).content.decode()
    assert "【" not in body and "ドラフト" not in body and "◯" not in body


@pytest.mark.parametrize("path", ["/terms/", "/privacy/"])
def test_運営者の名前と制定日が入っている(client, db, path):
    body = client.get(path).content.decode()
    assert "ikura1" in body and "制定日：2026年10月12日" in body


@pytest.mark.parametrize("path", ["/terms/", "/privacy/"])
@override_settings(CONTACT_FORM_URL=FORM)
def test_問い合わせフォームが決まっていれば_そのリンクが出る(client, db, path):
    body = client.get(path).content.decode()
    assert f'href="{FORM}"' in body and "準備中" not in body


@pytest.mark.parametrize("path", ["/terms/", "/privacy/"])
@override_settings(CONTACT_FORM_URL="")
def test_問い合わせフォームがまだなら_準備中と出す(client, db, path):
    assert "準備中" in client.get(path).content.decode()


def test_意見と不具合は_公開の場であることを断って_GitHub_に案内する(client, db):
    body = client.get("/terms/").content.decode()
    assert f'href="{ISSUES}"' in body and "誰でも読める" in body


def test_ポリシーには_実際に使っている事業者と保存先を書く(client, db):
    body = client.get("/privacy/").content.decode()
    assert "Google" in body and "Neon" in body and "シンガポール" in body
    assert "Render" not in body and "Cloudflare" not in body
    assert "Google Fonts" in body


def test_ポリシーには_まだない機能のことを書かない(client, db):
    body = client.get("/privacy/").content.decode()
    assert "写真" not in body and "MCP" not in body  # 実績は 2026-10-17 に入った（決定 063）


def test_ログイン画面から_規約とポリシーを開ける(client, db):
    body = client.get("/login/").content.decode()
    assert 'href="/terms/"' in body and 'href="/privacy/"' in body


def test_メニューから_規約とポリシーと報告の窓口を開ける(client_in):
    body = client_in.get("/menu/").content.decode()
    assert 'href="/terms/"' in body and 'href="/privacy/"' in body
    assert f'href="{ISSUES}/new/choose"' in body and "ご意見・不具合の報告" in body


def test_登録のときに記録する版は_規約は制定日_ポリシーは改定日と同じ():
    from apps.accounts.models import PRIVACY_VERSION, TERMS_VERSION

    assert (TERMS_VERSION, PRIVACY_VERSION) == ("2026-10-12", "2026-10-17")


def test_ポリシーには改定日が出る(client, db):
    assert "改定日：2026年10月17日" in client.get("/privacy/").content.decode()


def test_ポリシーの委託先に_問い合わせの受付_Googleフォーム_がある(client, db):
    body = client.get("/privacy/").content.decode()
    assert "Google LLC（Google フォーム）" in body and "問い合わせの受付" in body
