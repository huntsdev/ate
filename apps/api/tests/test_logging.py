import json
import logging
import sys

from sentinelforge.core.logging import JsonFormatter


def test_logs_are_structured_bounded_and_redact_credentials(settings):
    formatter = JsonFormatter(settings, "api")
    message = (
        "failed postgres://user:embedded-password@host/db "
        + settings.postgres_password.get_secret_value()
        + "x" * 2000
    )
    try:
        raise RuntimeError("exception-secret")
    except RuntimeError:
        record = logging.LogRecord("ate", logging.ERROR, "", 0, message, (), sys.exc_info())
    record.correlation_id = "synthetic-correlation"
    rendered = formatter.format(record)
    entry = json.loads(rendered)
    for secret in ("embedded-password", "synthetic-test-password", "exception-secret"):
        assert secret not in rendered
    assert entry["service"] == "api"
    assert entry["correlation_id"] == "synthetic-correlation"
    assert entry["error_type"] == "RuntimeError"
    assert len(entry["event"]) <= 1000
