"""本番の様子をまとめる（決定 046）。

GitHub Actions が Cloud Logging から取り出した JSON を読み、Markdown の報告と、エラーごとの Issue の中身を作る。
リポジトリは公開なので、**利用者のデータと秘密の値を一切含めない**。
- 経路の ID・数字・クエリは伏せる。知らない経路（管理画面の URL は秘密）は丸ごと伏せる
- エラーの本文と例外のメッセージは捨て、例外の種類と自前のコードの位置（ファイル:行 関数）だけを残す

使い方：python -m apps.core.ops_report --requests req.json --errors err.json --hours 24 [--issues issues.json]
"""

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import urlsplit

# 経路の先頭の部分。ここにないものは伏せる（経路を足したらここにも足す。足し忘れはテストが見つける）
KNOWN_ROOTS = {
    "", "login", "logout", "manifest.webmanifest", "install", "terms", "privacy", "grid", "menu", "timezone",
    "categories", "starters", "export", "account", "events", "logs", "accounts", "static", "health",
}  # fmt: skip
ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$|^\d+$", re.IGNORECASE)
# 2つ目以降の部分で、そのまま出してよい単語（アプリ自身の経路に出てくるものだけ）。
# 外から好きな単語を付けて、公開の報告に載せられないようにする（#74）。足し忘れはテストが見つける
KNOWN_PARTS = {
    "new", "edit", "remove", "restore", "move", "record", "record-sheet", "undo", "delete",  # イベントと記録
    "google", "login", "callback", "logout", "signup",  # ログイン（/accounts/）
    "css", "js", "icons", "vendor",  # 静的ファイルの置き場所（ファイル名は出さない）
}  # fmt: skip
FRAME = re.compile(r'^\s*File "(?:/app/)?((?:apps|config)/[^"]+)", line (\d+), in (\w+)')
EXCEPTION = re.compile(r"^([A-Za-z_][\w.]*(?:Error|Exception|Warning|Exit|Interrupt|DoesNotExist))\b")


def route_of(url: str) -> str:
    """URL を、利用者のデータを含まない経路の形にする。"""
    parts = urlsplit(url).path.split("/")[1:]
    if not parts or parts[0] not in KNOWN_ROOTS:
        return "/<その他>"
    shown = [parts[0]]
    for part in parts[1:]:
        if ID.match(part):
            shown.append("<id>")
        elif part == "" or part in KNOWN_PARTS:
            shown.append(part)
        else:
            shown.append("<?>")
    return "/" + "/".join(shown)


def _message(entry: dict) -> str:
    payload = entry.get("jsonPayload") or {}
    return payload.get("message") or entry.get("textPayload") or ""


@dataclass
class ErrorGroup:
    exception: str
    frames: list[str] = field(default_factory=list)
    count: int = 0

    @property
    def title(self) -> str:
        if not self.exception:
            return "トレースバックのないエラー"
        where = self.frames[-1] if self.frames else "自前のコードの外"
        return f"{self.exception}（{where}）"

    def as_issue(self) -> dict:
        frames = "\n".join(f"- `{f}`" for f in self.frames) or "- （自前のコードを通っていない）"
        body = (
            f"本番で `{self.exception or '（種類不明）'}` が {self.count} 回起きました。\n\n"
            f"通った自前のコード（古い順）：\n{frames}\n\n"
            "詳細（本文・リクエスト）は Error Reporting で見る。この Issue には利用者のデータを書かない。"
        )
        return {"title": f"本番のエラー：{self.title}", "body": body, "count": self.count}


def _parse(message: str) -> tuple[str, list[str]]:
    frames, exception = [], ""
    if "Traceback (most recent call last)" not in message:
        return exception, frames
    for line in message.splitlines():
        if m := FRAME.match(line):
            frames.append(f"{m[1]}:{m[2]} {m[3]}")
        elif not line.startswith(" ") and (m := EXCEPTION.match(line)):
            exception = m[1]
    return exception, frames


def error_groups(entries: list[dict]) -> list[ErrorGroup]:
    groups: dict[tuple, ErrorGroup] = {}
    for entry in entries:
        exception, frames = _parse(_message(entry))
        key = (exception, frames[-1] if frames else "")
        group = groups.setdefault(key, ErrorGroup(exception, frames))
        group.count += 1
    return sorted(groups.values(), key=lambda g: -g.count)


def _seconds(latency: str) -> float:
    try:
        return float(latency.rstrip("s"))
    except ValueError:
        return 0.0


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))]


def build_report(requests: list[dict], errors: list[dict], hours: int) -> str:
    http = [e["httpRequest"] for e in requests if "httpRequest" in e]
    statuses = Counter(f"{int(r.get('status', 0)) // 100}xx" for r in http)
    too_many = sum(1 for r in http if int(r.get("status", 0)) == 429)
    latencies = [_seconds(r.get("latency", "0s")) for r in http]
    failing = Counter(route_of(r.get("requestUrl", "")) for r in http if int(r.get("status", 0)) >= 500)
    slow = Counter(route_of(r.get("requestUrl", "")) for r in http if _seconds(r.get("latency", "0s")) >= 2)
    groups = error_groups(errors)

    lines = [f"## 本番の様子（直近 {hours} 時間）", ""]
    lines.append("異常なし" if not groups and not failing else "**要確認**：エラーまたは 5xx があります")
    lines += ["", f"- リクエスト：{len(http)} 件"]
    lines.append("- 状態：" + "、".join(f"{k}：{statuses.get(k, 0)}" for k in ("2xx", "3xx", "4xx", "5xx")))
    lines.append(f"- 429（レート制限）：{too_many}")
    lines.append(f"- 応答時間：中央値 {_percentile(latencies, 0.5):.2f} 秒、95% {_percentile(latencies, 0.95):.2f} 秒")
    if failing:
        lines += ["", "### 5xx が出た経路", *[f"- `{r}`：{n}" for r, n in failing.most_common(10)]]
    if slow:
        lines += ["", "### 2秒以上かかった経路", *[f"- `{r}`：{n}" for r, n in slow.most_common(10)]]
    if groups:
        lines += ["", "### エラー", *[f"- {g.title}：{g.count} 回" for g in groups]]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", required=True)
    parser.add_argument("--errors", required=True)
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--issues")
    args = parser.parse_args()
    with open(args.requests, encoding="utf-8") as f:
        requests = json.load(f)
    with open(args.errors, encoding="utf-8") as f:
        errors = json.load(f)
    print(build_report(requests, errors, args.hours))
    if args.issues:
        with open(args.issues, "w", encoding="utf-8") as f:
            json.dump([g.as_issue() for g in error_groups(errors)], f, ensure_ascii=False)


if __name__ == "__main__":
    main()
