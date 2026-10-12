"""本番のログの形（決定 046）。

Cloud Run は標準出力・標準エラーの1行が JSON なら、そのまま Cloud Logging の項目として読む。
`severity` で重要度を伝え（JSON でなければ標準エラーはすべて ERROR 扱いになる）、
例外は本文にトレースバックを入れて Error Reporting にまとめてもらう。
"""

import json
import logging

REPORTED_ERROR_EVENT = "type.googleapis.com/google.devtools.clouderrorreporting.v1beta1.ReportedErrorEvent"


class CloudRunFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        data = {"severity": record.levelname, "logger": record.name}
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}"
            data["@type"] = REPORTED_ERROR_EVENT
        data["message"] = message
        return json.dumps(data, ensure_ascii=False)
