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
