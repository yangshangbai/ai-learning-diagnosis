"""结构化 JSON 日志，每条携带 request_id，便于全链路追踪。

禁止在生产代码使用 print/console.log。通过 request_id_var（ContextVar）
在请求生命周期内传播请求 ID。
"""
import json
import logging
import sys
import time
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


logger = logging.getLogger("app")
if not logger.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(JsonFormatter())
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)
logger.propagate = False
