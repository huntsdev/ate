import pytest
from pydantic import ValidationError

from sentinelforge.core.config import ConfigurationError, Settings, get_settings


def test_defaults_and_encoded_database_password(settings):
    assert settings.postgres_host == "postgres"
    assert settings.ollama_url.host == "host.docker.internal"
    assert settings.readiness_timeout_seconds == 2
    changed = Settings(postgres_password="safe/@:password?#value")
    assert changed.database_url.password == "safe/@:password?#value"
    assert "safe/@:password?#value" not in str(changed.database_url)


@pytest.mark.parametrize(
    "values",
    [
        {"postgres_password": "short"},
        {"postgres_port": 0},
        {"readiness_timeout_seconds": 0},
        {"readiness_timeout_seconds": 100},
        {"ollama_url": "file:///tmp/model"},
        {"redis_url": "http://not-redis"},
        {"ollama_model": " "},
    ],
)
def test_invalid_configuration_is_rejected(settings, values):
    with pytest.raises(ValidationError):
        Settings(**values)


def test_missing_required_password_is_safe(monkeypatch):
    monkeypatch.delenv("ATE_POSTGRES_PASSWORD", raising=False)
    get_settings.cache_clear()
    with pytest.raises(ConfigurationError, match="postgres_password"):
        get_settings()


def test_invalid_environment_does_not_expose_inputs(monkeypatch):
    secret = "synthetic-secret@private-host"
    monkeypatch.setenv("ATE_POSTGRES_PASSWORD", secret)
    monkeypatch.setenv("ATE_REDIS_URL", f"https://user:{secret}")
    get_settings.cache_clear()
    with pytest.raises(ConfigurationError) as failure:
        get_settings()
    assert secret not in str(failure.value)
    assert str(failure.value) == "Invalid configuration fields: redis_url"


def test_ollama_is_configurable_and_never_required(settings, monkeypatch):
    monkeypatch.setenv("ATE_OLLAMA_URL", "http://127.0.0.1:12000")
    monkeypatch.setenv("ATE_OLLAMA_MODEL", "qwen-custom:test")
    custom = Settings()
    assert custom.ollama_url.port == 12000
    assert custom.ollama_model == "qwen-custom:test"
