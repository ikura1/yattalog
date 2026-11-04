"""運用の通知（Discord、決定 067）。Webhook の URL は秘密の値なので、どこにも出さない。"""

import json
import urllib.error

import pytest

from apps.core.ops_notify import build_payload, issues_message, main, webhook_ok

HOOK = "https://discord.com/api/webhooks/123456/abcdefSECRET"


class FakeOpener:
    def __init__(self, error=None):
        self.requests = []
        self.error = error

    def __call__(self, req, timeout):
        self.requests.append(req)
        if self.error:
            raise self.error
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b""


@pytest.mark.parametrize(
    "url",
    [HOOK, "https://discordapp.com/api/webhooks/1/x", "https://ptb.discord.com/api/webhooks/1/x"],
)
def test_DiscordのWebhookのURLは受け付ける(url):
    assert webhook_ok(url)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://discord.com/api/webhooks/1/x",  # 暗号化していない
        "https://discord.com/channels/1/2",  # Webhook ではない
        "https://evil.example/api/webhooks/1/x",
        "https://discord.com.evil.example/api/webhooks/1/x",
        "https://evil.example/?u=https://discord.com/api/webhooks/1/x",
    ],
)
def test_Discord以外の宛先には送らない(url):
    assert not webhook_ok(url)


def test_通知では_誰も呼び出さず_長すぎる文は切る():
    payload = build_payload("@everyone " + "あ" * 3000)
    assert payload["allowed_mentions"] == {"parse": []}  # @everyone などで人を呼ばない
    assert len(payload["content"]) <= 2000


def test_エラーのIssueは_題名と回数と実行のリンクだけを並べる():
    issues = [{"title": "ValueError（logs.record）", "count": 3, "body": "本文は送らない"}]
    text = issues_message(issues, 24, "https://github.com/x/y/actions/runs/1")
    assert "ValueError（logs.record）：3 回" in text
    assert "直近 24 時間" in text
    assert "https://github.com/x/y/actions/runs/1" in text
    assert "本文は送らない" not in text


def test_エラーがなければ_通知しない():
    assert issues_message([], 24, "https://example") is None


def test_通知先が未設定なら_何も送らずに終わる(monkeypatch, capsys):
    opener = FakeOpener()
    monkeypatch.delenv("OPS_WEBHOOK_URL", raising=False)
    assert main(["--message", "落ちた"], opener=opener) == 0
    assert opener.requests == []
    assert "未設定" in capsys.readouterr().out


def test_決めた文を_JSONでDiscordに送る(monkeypatch):
    opener = FakeOpener()
    monkeypatch.setenv("OPS_WEBHOOK_URL", HOOK)
    assert main(["--message", "本番に繋がらない"], opener=opener) == 0
    req = opener.requests[0]
    assert req.full_url == HOOK and req.get_method() == "POST"
    assert req.get_header("Content-type") == "application/json"
    assert "Yattalog" in req.get_header("User-agent")  # 既定の Python-urllib だと Discord に断られる
    assert json.loads(req.data)["content"] == "本番に繋がらない"


def test_IssueのファイルからErrorの知らせを作って送る(monkeypatch, tmp_path):
    opener = FakeOpener()
    f = tmp_path / "issues.json"
    f.write_text(json.dumps([{"title": "KeyError（x）", "count": 1, "body": ""}]), encoding="utf-8")
    monkeypatch.setenv("OPS_WEBHOOK_URL", HOOK)
    assert main(["--issues", str(f), "--hours", "24", "--run-url", "https://r"], opener=opener) == 0
    assert "KeyError（x）：1 回" in json.loads(opener.requests[0].data)["content"]


def test_Issueが空なら送らない(monkeypatch, tmp_path):
    opener = FakeOpener()
    f = tmp_path / "issues.json"
    f.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("OPS_WEBHOOK_URL", HOOK)
    assert main(["--issues", str(f), "--run-url", "https://r"], opener=opener) == 0
    assert opener.requests == []


def test_宛先がおかしければ送らず_URLは出さない(monkeypatch, capsys):
    opener = FakeOpener()
    monkeypatch.setenv("OPS_WEBHOOK_URL", "https://evil.example/hookSECRET")
    assert main(["--message", "x"], opener=opener) == 0
    assert opener.requests == []
    out = capsys.readouterr()
    assert "SECRET" not in out.out + out.err
    assert "::warning" in out.out


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.HTTPError(HOOK, 404, "Not Found", {}, None),
        urllib.error.URLError(f"cannot reach {HOOK}"),
        TimeoutError(HOOK),
    ],
)
def test_送れなくても監視は止めず_URLは出さない(monkeypatch, capsys, error):
    monkeypatch.setenv("OPS_WEBHOOK_URL", HOOK)
    assert main(["--message", "x"], opener=FakeOpener(error)) == 0  # 通知の失敗で、監視の実行を失敗にしない
    out = capsys.readouterr()
    assert "SECRET" not in out.out + out.err and "123456" not in out.out + out.err
    assert "::warning" in out.out


def _steps(name):
    """ワークフローを、手順（「      - 」で始まる塊）ごとに分ける。"""
    from pathlib import Path

    from django.conf import settings

    text = Path(settings.BASE_DIR, ".github", "workflows", name).read_text()
    return text.split("\n      - ")[1:]


@pytest.mark.parametrize("name", ["ops-report.yml", "uptime.yml"])
def test_監視のワークフローは_困ったときだけ通知し_Webhookは通知の手順にだけ渡す(name):
    holders = [s for s in _steps(name) if "OPS_WEBHOOK_URL" in s]
    assert holders
    for step in holders:
        assert "apps.core.ops_notify" in step
        assert "OPS_WEBHOOK_URL: ${{ secrets.OPS_WEBHOOK_URL }}" in step
        assert "if: failure()" in step or name != "uptime.yml"  # 応答があるときは送らない


def test_送る関数も_Discord以外の宛先は開かない():
    from apps.core.ops_notify import send

    opener = FakeOpener()
    with pytest.raises(ValueError):
        send("file:///etc/passwd", "x", opener)
    assert opener.requests == []
