import pytest

from sentinelforge.core.config import Settings, get_settings


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("ATE_POSTGRES_PASSWORD", "synthetic-test-password")
    get_settings.cache_clear()
    yield Settings()
    get_settings.cache_clear()
