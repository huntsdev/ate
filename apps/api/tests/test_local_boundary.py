import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from sentinelforge.core.config import Settings
from sentinelforge.main import create_app


@pytest.mark.parametrize(
    "values",
    [
        {"trusted_hosts": ["*"]},
        {"trusted_hosts": ["192.168.1.2"]},
        {"browser_origins": ["https://attacker.invalid"]},
        {"browser_origins": ["http://localhost/path"]},
        {"browser_origins": ["http://user:secret@localhost"]},
    ],
)
def test_local_mode_cannot_be_configured_for_external_origins(settings, values):
    with pytest.raises(ValidationError):
        Settings(**values)


def test_preflight_and_untrusted_host_fail_without_database(settings):
    with TestClient(create_app(settings)) as client:
        response = client.options("/api/v1/cases", headers={"Origin": "https://attacker.invalid"})
        assert response.status_code == 403
        assert "access-control-allow-origin" not in response.headers
        response = client.get("/api/v1/health", headers={"Host": "attacker.invalid"})
        assert response.status_code == 400 and response.json()["code"] == "invalid_host"
