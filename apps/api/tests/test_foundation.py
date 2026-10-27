import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from sentinelforge.core.health import ReadinessChecker
from sentinelforge.main import create_app

ROOT = Path(__file__).resolve().parents[3]


def test_health_contract_and_no_business_routes(settings):
    async def ok():
        pass

    with TestClient(
        create_app(settings, ReadinessChecker({"postgres": ok, "redis": ok}, 0.1))
    ) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["service"] == "ate"
        assert set(client.get("/openapi.json").json()["paths"]) == {
            "/api/v1/health",
            "/api/v1/health/live",
            "/api/v1/health/ready",
        }


def test_synthetic_fixtures_are_deterministic_and_linked():
    fixture_dir = ROOT / "tests/fixtures"
    alert = json.loads((fixture_dir / "synthetic_alert.json").read_text())
    case = json.loads((fixture_dir / "synthetic_case.json").read_text())
    assert alert["synthetic"] is case["synthetic"] is True
    assert alert["external_alert_id"] in case["alert_ids"]
    assert alert["host"].endswith(".invalid")
    assert case["status"] == "new"
    assert case["disposition"] is None


def test_compose_is_private_persistent_and_has_shared_networks():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())
    services = compose["services"]
    assert "ollama" not in services
    for name in ("postgres", "redis"):
        assert "ports" not in services[name]
        assert services[name]["volumes"]
        assert services[name]["healthcheck"]
    for name in ("elasticsearch", "kibana"):
        assert services[name]["profiles"] == ["elastic"]
        assert name not in services["api"]["depends_on"]
    for service in services.values():
        for port in service.get("ports", []):
            assert port.startswith("127.0.0.1:")
    for left, right in (("web", "api"), ("api", "postgres"), ("api", "redis"), ("worker", "redis")):
        assert set(services[left]["networks"]) & set(services[right]["networks"])
    assert compose["networks"]["backend"]["internal"] is True
    assert set(compose["volumes"]) == {"postgres_data", "redis_data", "elastic_data"}
