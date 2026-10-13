"""本番のログの形（Cloud Logging が読める1行1件の JSON）。"""

import json
import logging
import sys

from apps.core.logging import CloudRunFormatter


def record(level=logging.INFO, msg="こんにちは %s", args=("世界",), exc_info=None):
    return logging.LogRecord("django.request", level, __file__, 1, msg, args, exc_info)


def test_1件を1行のJSONにし重要度と本文を入れる():
    line = CloudRunFormatter().format(record(level=logging.WARNING))
    assert "\n" not in line
    data = json.loads(line)
    assert data["severity"] == "WARNING"
    assert data["message"] == "こんにちは 世界"
    assert data["logger"] == "django.request"


def test_例外は本文にトレースバックを含めエラー報告の対象にする():
    try:
        raise ValueError("中身")
    except ValueError:
        exc_info = sys.exc_info()
    data = json.loads(CloudRunFormatter().format(record(level=logging.ERROR, exc_info=exc_info)))
    assert data["severity"] == "ERROR"
    assert data["message"].startswith("こんにちは 世界\nTraceback (most recent call last):")
    assert "ValueError: 中身" in data["message"]
    assert data["@type"].endswith("ReportedErrorEvent")


def test_例外のないエラーはエラー報告の対象にしない():
    data = json.loads(CloudRunFormatter().format(record(level=logging.ERROR)))
    assert "@type" not in data


# --- 利用者のデータをログに出さない（レビュー S11） ---


def db_error():
    """PostgreSQL の一意制約のエラー。DETAIL の行に、入力された値がそのまま入る。"""
    message = (
        'duplicate key value violates unique constraint "uniq_category_name"\n'
        "DETAIL:  Key (space_id, name)=(0b1c2d3e-4f50-4a6b-8c7d-9e0f1a2b3c4d, ひみつの病院) already exists."
    )
    try:
        raise RuntimeError(message)
    except RuntimeError:
        return sys.exc_info()


def test_DB_のエラーの_DETAIL_の行は_値を伏せる():
    data = json.loads(CloudRunFormatter().format(record(level=logging.ERROR, exc_info=db_error())))

    assert "ひみつの病院" not in data["message"]
    assert "DETAIL: （値は伏せています）" in data["message"]


def test_伏せても_どの制約で落ちたかと_どこで落ちたかは残る():
    data = json.loads(CloudRunFormatter().format(record(level=logging.ERROR, exc_info=db_error())))

    assert 'unique constraint "uniq_category_name"' in data["message"]
    assert "Traceback (most recent call last):" in data["message"] and "test_logging.py" in data["message"]
    assert data["@type"].endswith("ReportedErrorEvent")


def test_本文に入った_DETAIL_の行も伏せる():
    message = "失敗\nDETAIL:  Key (email)=(a@example.com) exists"
    line = CloudRunFormatter().format(record(level=logging.ERROR, msg=message, args=()))
    assert "a@example.com" not in line and "失敗" in json.loads(line)["message"]
