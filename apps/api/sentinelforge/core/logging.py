import json
import logging
import re
from datetime import UTC, datetime

from sentinelforge.core.config import Settings


class JsonFormatter(logging.Formatter):
    def __init__(self, settings: Settings, service: str):
        super().__init__()
        self.service = service
        self.secrets = [settings.postgres_password.get_secret_value()]
        if settings.redis_url.password:
            self.secrets.append(settings.redis_url.password)

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        for secret in self.secrets:
            message = message.replace(secret, "[redacted]")
        message = re.sub(r"(\w+://)[^\s/@]+:[^\s/@]+@", r"\1[redacted]@", message)
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "service": self.service,
            "level": record.levelname,
            "event": message[:1000],
        }
        for key in ("correlation_id", "status_code", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        # Exception messages and tracebacks can contain connection credentials.
        if record.exc_info and record.exc_info[0]:
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(settings: Settings, service: str = "api") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(settings, service))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "celery"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
