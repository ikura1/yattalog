"""データの書き出し（SPEC 3.11.2、決定 021・039）。

写真がまだないので、ZIP はその場で作って返す（バックグラウンド処理もファイルの保存もしない）。
"""

import csv
import io
import json
import zipfile
from datetime import datetime

from apps.events.models import Category, Event, Log
from apps.events.services import achievements as ach_svc
from apps.events.services.dates import zone
from apps.spaces.services import personal_space

FORMAT = "yattalog-export"
VERSION = 1
BOM = "﻿"  # Excel が UTF-8 と判断できるようにする
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r", "\n")

LOG_HEADER = ["イベント名", "カテゴリ", "日付", "時刻", "タイムゾーン", "メモ", "写真のファイル名", "記録元"]
EVENT_HEADER = ["名前", "アイコン", "色", "カテゴリ", "連続記録の単位", "アーカイブ済み", "作成日"]


def csv_safe(value: str) -> str:
    """表計算ソフトで数式として実行されないよう、危ない始まり方の値には先頭に ' を付ける（決定 029）。"""
    return "'" + value if value.startswith(FORMULA_STARTS) else value


def export_filename(user, now: datetime) -> str:
    return f"yattalog-{now.astimezone(zone(user.timezone)):%Y%m%d}.zip"


def _csv(header: list[str], rows: list[list[str]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows([[csv_safe(cell) for cell in row] for row in rows])
    return BOM + out.getvalue()


def _log_row(log: Log) -> list[str]:
    at = log.occurred_at.astimezone(zone(log.timezone)) if log.occurred_at else None
    return [
        log.event.name,
        log.event.category.name if log.event.category else "",
        log.local_date.isoformat(),
        f"{at:%H:%M}" if at else "",
        log.timezone,
        log.memo,
        "",  # 写真（β で追加）
        log.get_source_display(),
    ]


def _event_row(event: Event, tz) -> list[str]:
    return [
        event.name,
        event.emoji,
        event.color,
        event.category.name if event.category else "",
        event.get_streak_unit_display(),
        "はい" if event.is_archived else "いいえ",
        event.created_at.astimezone(tz).date().isoformat(),
    ]


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _achievements(user) -> list[dict]:
    """解除した実績（決定 063）。"""
    return [{"code": a.code, "name": a.name, "unlocked_at": _iso(at)} for a, at in ach_svc.listing(user) if at]


def _data(user, now: datetime, categories, events, logs) -> dict:
    return {
        "format": FORMAT,
        "version": VERSION,
        "exported_at": now.isoformat(),
        "user": {"display_name": user.display_name, "timezone": user.timezone},
        "categories": [
            {
                "id": str(c.id),
                "name": c.name,
                "emoji": c.emoji,
                "sort_key": c.sort_key,
                "created_at": _iso(c.created_at),
            }
            for c in categories
        ],
        "events": [
            {
                "id": str(e.id),
                "name": e.name,
                "emoji": e.emoji,
                "color": e.color,
                "streak_unit": e.streak_unit,
                "category_id": str(e.category_id) if e.category_id else None,
                "sort_key": e.sort_key,
                "is_archived": e.is_archived,
                "archived_at": _iso(e.archived_at),
                "created_at": _iso(e.created_at),
            }
            for e in events
        ],
        "logs": [
            {
                "id": str(log.id),
                "event_id": str(log.event_id),
                "local_date": log.local_date.isoformat(),
                "occurred_at": _iso(log.occurred_at),
                "timezone": log.timezone,
                "memo": log.memo,
                "source": log.source,
                "created_at": _iso(log.created_at),
            }
            for log in logs
        ],
        "achievements": _achievements(user),
    }


def build_export(user, now: datetime) -> bytes:
    """ユーザーの全データを ZIP にして返す。中身は自分のスペースのものだけ。"""
    space = personal_space(user)
    tz = zone(user.timezone)
    categories = list(Category.objects.filter(space=space).order_by("sort_key"))
    events = list(Event.objects.filter(space=space).select_related("category").order_by("sort_key"))
    logs = list(Log.objects.filter(space=space).select_related("event__category"))

    files = {
        "logs.csv": _csv(LOG_HEADER, [_log_row(log) for log in logs]),
        "events.csv": _csv(EVENT_HEADER, [_event_row(event, tz) for event in events]),
        "data.json": json.dumps(_data(user, now, categories, events, logs), ensure_ascii=False, indent=2),
    }
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in files.items():
            z.writestr(name, text.encode("utf-8"))
    return out.getvalue()
