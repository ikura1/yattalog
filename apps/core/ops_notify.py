"""運用の通知を Discord に送る（決定 067）。Ops report と死活監視が、困ったことを見つけたときだけ使う。

    OPS_WEBHOOK_URL=... python -m apps.core.ops_notify --message "本番に繋がらない"
    OPS_WEBHOOK_URL=... python -m apps.core.ops_notify --issues issues.json --hours 24 --run-url URL

送るのは、Issue の題名・回数・実行のリンクだけ（どれも公開のリポジトリに出ているもの）。
Webhook の URL は秘密の値なので、どこにも出さない。未設定なら何もしない。
通知に失敗しても、監視の実行は失敗にしない（警告だけ出す）。
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit

USER_AGENT = "Yattalog-ops (https://github.com/ikura1/yattalog, 1.0)"  # 既定の Python-urllib だと Discord に断られる
HOSTS = {"discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com"}
LIMIT = 2000  # Discord の1通の上限（文字）
TIMEOUT = 10


def webhook_ok(url: str) -> bool:
    """Discord の Webhook の URL か（打ち間違いや、ほかの宛先に送らないため）。"""
    parts = urlsplit(url or "")
    return parts.scheme == "https" and parts.hostname in HOSTS and parts.path.startswith("/api/webhooks/")


def build_payload(text: str) -> dict:
    return {
        "username": "Yattalog 運用",
        "content": text[:LIMIT],
        "allowed_mentions": {"parse": []},  # @everyone などが含まれても、人を呼ばない
    }


def issues_message(issues: list[dict], hours: int, run_url: str) -> str | None:
    if not issues:
        return None
    lines = [f"⚠️ Yattalog：直近 {hours} 時間でエラーがありました"]
    lines += [f"- {i['title']}：{i['count']} 回" for i in issues]
    lines.append(run_url)
    return "\n".join(lines)


def send(url: str, text: str, opener=urllib.request.urlopen) -> None:
    if not webhook_ok(url):  # https の Discord だけに送る（file: などは開かない）
        raise ValueError("not a Discord webhook")
    req = urllib.request.Request(  # noqa: S310
        url,
        data=json.dumps(build_payload(text)).encode(),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    with opener(req, timeout=TIMEOUT) as resp:
        resp.read()


def _warn(message: str) -> None:
    print(f"::warning title=ops-notify::{message}")


def main(argv: list[str] | None = None, opener=urllib.request.urlopen) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message")
    parser.add_argument("--issues")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--run-url", default="")
    args = parser.parse_args(argv)

    url = os.environ.get("OPS_WEBHOOK_URL", "")
    if not url:
        print("通知先（OPS_WEBHOOK_URL）が未設定なので、送りません")
        return 0
    if not webhook_ok(url):
        _warn("OPS_WEBHOOK_URL が Discord の Webhook の形ではないので、送りません")
        return 0

    if args.issues:
        with open(args.issues, encoding="utf-8") as f:
            text = issues_message(json.load(f), args.hours, args.run_url)
    else:
        text = args.message
    if not text:
        return 0

    try:
        send(url, text, opener)
    except urllib.error.HTTPError as e:
        _warn(f"Discord に送れませんでした（HTTP {e.code}）")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        _warn(f"Discord に送れませんでした（{type(e).__name__}）")  # 本文に URL が入ることがあるので、種類だけ出す
    return 0


if __name__ == "__main__":
    sys.exit(main())
