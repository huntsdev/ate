import asyncio
import sys

import pytest

from sentinelforge.core.config import Settings, get_settings


def pytest_asyncio_loop_factories():
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return None


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("ATE_POSTGRES_PASSWORD", "synthetic-test-password")
    get_settings.cache_clear()
    yield Settings().model_copy(update={"trusted_hosts": ["testserver", "127.0.0.1", "localhost"]})
    get_settings.cache_clear()
