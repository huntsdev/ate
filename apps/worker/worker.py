from typing import Any

from celery import Celery
from celery.signals import after_setup_logger

from sentinelforge.core.config import get_settings
from sentinelforge.core.logging import configure_logging

settings = get_settings()
celery_app = Celery("ate", broker=str(settings.redis_url), backend=str(settings.redis_url))
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=300,
    task_time_limit=30,
    task_soft_time_limit=20,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=3,
    broker_transport_options={"socket_connect_timeout": 3, "socket_timeout": 3},
    result_backend_transport_options={"socket_connect_timeout": 3, "socket_timeout": 3},
    worker_hijack_root_logger=False,
    worker_send_task_events=False,
    task_send_sent_event=False,
)


@after_setup_logger.connect
def setup_worker_logging(**kwargs: Any) -> None:
    configure_logging(settings, "worker")


@celery_app.task(name="ate.foundation.noop")
def noop() -> dict[str, str]:
    """Synthetic infrastructure smoke check only; no business jobs in Phase 0."""
    return {"status": "ok"}
