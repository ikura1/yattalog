"""Ops report 用に、Cloud Logging からログを取る（決定 046、#72）。

この処理は GitHub のランナー（Google Cloud の外）で動く。利用者の IP アドレスやブラウザの種類を持ち出さないよう、
集計に要る項目だけを `fields` で指定して、Google の側で絞ってもらう。gcloud の --format は、手元に全部を
取ってきてから絞るので使わない。

    python -m apps.core.ops_fetch --project <ID> --hours 24 --requests requests.json --errors errors.json

アクセストークンは、環境変数 GCP_ACCESS_TOKEN で渡す。
"""

import argparse
import json
import os
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlsplit, urlunsplit

API = "https://logging.googleapis.com/v2/entries:list"
PAGE_SIZE = 1000
SERVICE = 'resource.type="cloud_run_revision" AND resource.labels.service_name="yattalog"'
REQUEST_LOG = 'log_id("run.googleapis.com/requests")'

# 持ち出す項目。IP アドレス（remoteIp）・ブラウザの種類（userAgent）・参照元（referer）は求めない
REQUEST_FIELDS = "entries(httpRequest(status,latency,requestUrl)),nextPageToken"
# jsonPayload は中の項目を選べない（選ぶと 400 になる）。中身はアプリが出す severity・logger・message だけ（logging.py）
ERROR_FIELDS = "entries(severity,textPayload,jsonPayload),nextPageToken"

Api = Callable[[str, dict], dict]


def fetch(
    api: Api, project: str, log_filter: str, fields: str, *, hours: int, now: datetime, max_pages: int = 20
) -> list[dict]:
    """条件に合うログを、指定した項目だけ取る。新しい順に、最大 max_pages ページまで。"""
    since = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{API}?fields={quote(fields, safe='()')}"
    body = {
        "resourceNames": [f"projects/{project}"],
        "filter": f'({log_filter}) AND timestamp>="{since}"',
        "orderBy": "timestamp desc",
        "pageSize": PAGE_SIZE,
    }
    entries: list[dict] = []
    for _ in range(max_pages):
        page = api(url, body)
        entries += page.get("entries", [])
        if not (token := page.get("nextPageToken")):
            break
        body = {**body, "pageToken": token}
    return entries


def strip_query(entries: list[dict]) -> list[dict]:
    """URL のクエリ文字列を落とす（OAuth の認可コードなどが入るため、#49）。"""
    cleaned = []
    for entry in entries:
        request = entry.get("httpRequest")
        if request and "requestUrl" in request:
            parts = urlsplit(request["requestUrl"])
            url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
            entry = {**entry, "httpRequest": {**request, "requestUrl": url}}
        cleaned.append(entry)
    return cleaned


def google_api(token: str) -> Api:
    def call(url: str, body: dict) -> dict:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        # URL は上の定数（API）から作ったものだけ
        request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")  # noqa: S310
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            return json.load(response)

    return call


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--requests", required=True)
    parser.add_argument("--errors", required=True)
    args = parser.parse_args()
    api = google_api(os.environ["GCP_ACCESS_TOKEN"])
    now = datetime.now(UTC)
    requests = fetch(api, args.project, f"{SERVICE} AND {REQUEST_LOG}", REQUEST_FIELDS, hours=args.hours, now=now)
    errors = fetch(
        api,
        args.project,
        f"{SERVICE} AND severity>=ERROR AND NOT {REQUEST_LOG}",
        ERROR_FIELDS,
        hours=args.hours,
        now=now,
        max_pages=1,
    )
    with open(args.requests, "w", encoding="utf-8") as f:
        json.dump(strip_query(requests), f)
    with open(args.errors, "w", encoding="utf-8") as f:
        json.dump(errors, f)
    # 件数だけを出す（中身は出さない）
    print(f"requests={len(requests)} errors={len(errors)}")


if __name__ == "__main__":
    main()
