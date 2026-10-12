"""Ops report 用のログの取得（#72）。Google Cloud の外へ持ち出す項目を、集計に要るものだけに絞る。"""

import json
from datetime import UTC, datetime

from apps.core.ops_fetch import ERROR_FIELDS, REQUEST_FIELDS, fetch, strip_query

NOW = datetime(2026, 10, 13, 0, 0, tzinfo=UTC)


class FakeApi:
    """Cloud Logging の代わり。呼ばれた内容を覚えておき、用意したページを順に返す。"""

    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def __call__(self, url, body):
        self.calls.append((url, body))
        return self.pages.pop(0)


def test_アクセスログで求めるのは_状態と応答時間と_URL_だけ():
    assert "remoteIp" not in REQUEST_FIELDS and "userAgent" not in REQUEST_FIELDS and "referer" not in REQUEST_FIELDS
    assert REQUEST_FIELDS == "entries(httpRequest(status,latency,requestUrl)),nextPageToken"


def test_エラーのログで求めるのは_本文と重要度だけ():
    # jsonPayload の中の項目は選べない（選ぶと本物の API が 400 を返す）。中身はアプリのログだけ
    assert ERROR_FIELDS == "entries(severity,textPayload,jsonPayload),nextPageToken"
    assert "httpRequest" not in ERROR_FIELDS and "labels" not in ERROR_FIELDS


def test_求める項目は_fields_として_Google_に伝える_返ってくる時点で絞られている():
    api = FakeApi([{"entries": [{"httpRequest": {"status": 200}}]}])

    fetch(api, "yattalog-x", 'resource.type="cloud_run_revision"', REQUEST_FIELDS, hours=24, now=NOW)

    url, body = api.calls[0]
    assert url == "https://logging.googleapis.com/v2/entries:list?fields=" + REQUEST_FIELDS.replace(",", "%2C")
    assert body["resourceNames"] == ["projects/yattalog-x"] and body["pageSize"] == 1000
    assert body["filter"] == '(resource.type="cloud_run_revision") AND timestamp>="2026-10-12T00:00:00Z"'


def test_続きのページがあれば_最後まで取りに行く():
    api = FakeApi([{"entries": [{"a": 1}], "nextPageToken": "p2"}, {"entries": [{"a": 2}]}])

    got = fetch(api, "p", "f", REQUEST_FIELDS, hours=1, now=NOW)

    assert got == [{"a": 1}, {"a": 2}]
    assert "pageToken" not in api.calls[0][1] and api.calls[1][1]["pageToken"] == "p2"


def test_取りすぎないよう_ページ数に上限がある():
    api = FakeApi([{"entries": [{"n": i}], "nextPageToken": "more"} for i in range(50)])

    got = fetch(api, "p", "f", REQUEST_FIELDS, hours=1, now=NOW, max_pages=3)

    assert len(got) == 3 and len(api.calls) == 3


def test_ログが1件もなければ_空の一覧():
    assert fetch(FakeApi([{}]), "p", "f", REQUEST_FIELDS, hours=1, now=NOW) == []


def test_URL_のクエリ文字列は_すぐに落とす():
    """ログイン時の URL には OAuth の認可コードが入っている（#49）。ファイルに書く前に落とす。"""
    entries = [
        {"httpRequest": {"requestUrl": "https://x.example/accounts/google/login/callback/?code=SECRET&state=abc"}},
        {"httpRequest": {"requestUrl": "https://x.example/events/1/"}},
        {"textPayload": "no request here"},
    ]

    cleaned = strip_query(entries)

    assert "SECRET" not in json.dumps(cleaned)
    assert [e.get("httpRequest", {}).get("requestUrl") for e in cleaned] == [
        "https://x.example/accounts/google/login/callback/",
        "https://x.example/events/1/",
        None,
    ]
