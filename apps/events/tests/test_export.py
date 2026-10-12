"""データの書き出し（SPEC 3.11.2、決定 021・039）。ZIP の中身を確かめる。"""

import csv
import io
import json
import uuid
import zipfile
from datetime import time, timedelta

import pytest

from apps.core.testing import NOW, TODAY, new_user
from apps.events.services import events as ev_svc
from apps.events.services import logs as log_svc
from apps.events.services.export import build_export, csv_safe, export_filename
from apps.events.services.logs import When

BOM = "﻿"


def unzip(data: bytes) -> dict[str, str]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {name: z.read(name).decode("utf-8") for name in z.namelist()}


def rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text.removeprefix(BOM))))


@pytest.fixture
def exported(user):
    house = ev_svc.create_category(user, "家事", emoji="🧹")
    sheets = ev_svc.create_event(
        user, name="シーツ交換", emoji="🛏️", color="sky", streak_unit="week", category_id=house.id
    )
    haircut = ev_svc.create_event(user, name="散髪", emoji="✂️", color="grape", streak_unit="month")
    log_svc.record(user, sheets.id, uuid.uuid7(), memo="冬用に替えた")
    log_svc.record(user, haircut.id, uuid.uuid7(), When(date=TODAY - timedelta(32)))
    ev_svc.set_archived(user, haircut.id, True)
    return unzip(build_export(user, NOW))


def test_ZIP_には_3つのファイルが入っている(exported):
    assert sorted(exported) == ["data.json", "events.csv", "logs.csv"]


def test_CSV_は_Excel_で文字化けしないよう_BOM_つきの_UTF8(exported):
    assert exported["logs.csv"].startswith(BOM) and exported["events.csv"].startswith(BOM)


def test_logs_csv_は_1行1記録で_新しい順(exported):
    assert rows(exported["logs.csv"]) == [
        ["イベント名", "カテゴリ", "日付", "時刻", "タイムゾーン", "メモ", "写真のファイル名", "記録元"],
        ["シーツ交換", "家事", "2026-10-10", "12:00", "Asia/Tokyo", "冬用に替えた", "", "アプリ"],
        ["散髪", "", "2026-09-08", "", "", "", "", "アプリ"],
    ]


def test_events_csv_は_1行1イベントで_ホームの並び順_アーカイブ済みも含む(exported):
    assert rows(exported["events.csv"]) == [
        ["名前", "アイコン", "色", "カテゴリ", "連続記録の単位", "アーカイブ済み", "作成日"],
        ["散髪", "✂️", "grape", "", "毎月", "はい", "2026-10-10"],
        ["シーツ交換", "🛏️", "sky", "家事", "毎週", "いいえ", "2026-10-10"],
    ]


def test_data_json_には_取り込み直せるだけの全データが入っている(exported):
    data = json.loads(exported["data.json"])
    assert (data["format"], data["version"], data["exported_at"]) == ("yattalog-export", 1, "2026-10-10T03:00:00+00:00")
    assert data["user"] == {"display_name": "", "timezone": "Asia/Tokyo"}
    assert [(c["name"], c["emoji"]) for c in data["categories"]] == [("家事", "🧹")]
    assert {e["name"]: (e["streak_unit"], e["is_archived"]) for e in data["events"]} == {
        "シーツ交換": ("week", False),
        "散髪": ("month", True),
    }
    by_memo = {log["memo"]: log for log in data["logs"]}
    assert by_memo["冬用に替えた"]["occurred_at"] == "2026-10-10T03:00:00+00:00"
    assert (by_memo[""]["local_date"], by_memo[""]["occurred_at"], by_memo[""]["timezone"]) == ("2026-09-08", None, "")
    event_ids = {e["id"] for e in data["events"]}
    assert all(log["event_id"] in event_ids for log in data["logs"])
    assert data["events"][0]["category_id"] in {c["id"] for c in data["categories"]} | {None}


def test_他人のデータは入らない(user):
    other = new_user(email="b@example.com")
    theirs = ev_svc.create_event(other, name="ひみつの習慣", emoji="🤫", color="pink")
    log_svc.record(other, theirs.id, uuid.uuid7(), memo="ないしょ")
    ev_svc.create_category(other, "ひみつ")

    everything = "".join(unzip(build_export(user, NOW)).values())

    assert "ひみつ" not in everything and "ないしょ" not in everything and "b@example.com" not in everything


@pytest.mark.parametrize("dangerous", ["=1+1", "+SUM(A1)", "-2", "@cmd", "\tx", "\rx", "\nx"])
def test_数式として実行されそうな値は_先頭に_アポストロフィを付ける(dangerous):
    """CSV インジェクション対策（決定 029）。"""
    assert csv_safe(dangerous) == "'" + dangerous


@pytest.mark.parametrize("harmless", ["シーツ交換", "3日ぶり", "a=b", "", "🪴"])
def test_ふつうの値は_そのまま(harmless):
    assert csv_safe(harmless) == harmless


def test_CSV_では_名前とメモを無害化し_data_json_は元の値のまま(user):
    event = ev_svc.create_event(user, name="=1+1", emoji="⭐", color="sky")
    ev_svc.create_category(user, "@家事")
    log_svc.record(user, event.id, uuid.uuid7(), memo="+SUM(A1)")

    files = unzip(build_export(user, NOW))

    assert rows(files["logs.csv"])[1][0] == "'=1+1" and rows(files["logs.csv"])[1][5] == "'+SUM(A1)"
    assert rows(files["events.csv"])[1][0] == "'=1+1"
    data = json.loads(files["data.json"])
    assert (data["events"][0]["name"], data["logs"][0]["memo"], data["categories"][0]["name"]) == (
        "=1+1",
        "+SUM(A1)",
        "@家事",
    )


def test_時刻は_記録したときのタイムゾーンで出す(user):
    event = ev_svc.create_event(user, name="水やり", emoji="🪴", color="leaf")
    log_svc.record(user, event.id, uuid.uuid7(), When(date=TODAY, time=time(7, 5)))
    user.timezone = "America/Los_Angeles"
    user.save()

    assert rows(unzip(build_export(user, NOW))["logs.csv"])[1][2:5] == ["2026-10-10", "07:05", "Asia/Tokyo"]


def test_何も記録していなくても_見出しだけの_CSV_ができる(user):
    files = unzip(build_export(user, NOW))
    assert len(rows(files["logs.csv"])) == 1 and len(rows(files["events.csv"])) == 1
    assert json.loads(files["data.json"])["logs"] == []


def test_ファイル名には_書き出した日が_ユーザーのタイムゾーンで入る(user):
    assert export_filename(user, NOW) == "yattalog-20261010.zip"
