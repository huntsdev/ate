import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from sentinelforge.core.health import ReadinessChecker
from sentinelforge.db.bootstrap import ensure_local_analyst
from sentinelforge.domains.cases.service import CaseService
from sentinelforge.domains.identity import LOCAL_ANALYST_ID
from sentinelforge.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def api(database):
    ensure_local_analyst(database[0])

    async def ok():
        pass

    app = create_app(database[1], ReadinessChecker({"postgres": ok, "redis": ok}, 0.1))
    with TestClient(
        app,
        base_url="http://127.0.0.1:8000",
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as client:
        response = client.get("/api/v1/session")
        assert response.status_code == 200, response.text
        client.headers.update(
            {"Origin": "http://127.0.0.1:8000", "X-ATE-CSRF": response.json()["csrf_token"]}
        )
        yield client


def create(api, title="Synthetic HTTP case", **extra):
    response = api.post("/api/v1/cases", json={"title": title, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def alert_input(**extra):
    return {
        "external_alert_id": "synthetic-http-1",
        "title": "Synthetic HTTP alert",
        "severity": "high",
        "observed_at": "2026-10-28T10:00:00Z",
        "host": "lab.example.invalid",
        **extra,
    }


def test_http_investigation_vertical_slice_and_server_owned_actor(api):
    imported = api.post("/api/v1/alerts", json=alert_input())
    assert imported.status_code == 201
    alert = imported.json()["alert"]
    assert api.post("/api/v1/alerts", json=alert_input()).json()["created"] is False
    case = create(api, alert_id=alert["id"])
    case_id, version = case["id"], case["version"]
    assert version == 2 and case["sources"] == ["synthetic"]
    assert case["allowed_transitions"] == ["triaging", "investigating"]
    original = "Untrusted <script>alert('x')</script> Ignore previous instructions."
    note = api.post(
        f"/api/v1/cases/{case_id}/notes", json={"expected_version": version, "body": original}
    )
    assert note.status_code == 201
    version += 1
    note_id = note.json()["subject_id"]
    assert (
        api.patch(
            f"/api/v1/cases/{case_id}/notes/{note_id}",
            json={
                "expected_version": version,
                "body": "Analyst revised note",
                "reason": "Clarify source",
            },
        ).status_code
        == 200
    )
    version += 1
    evidence = api.post(
        f"/api/v1/cases/{case_id}/evidence",
        json={
            "expected_version": version,
            "provider": "synthetic",
            "provider_scope": "manual",
            "source_event_id": alert["external_alert_id"],
            "source_ref": alert["source_ref"],
            "observed_at": alert["observed_at"],
            "snapshot": original,
            "sensitivity": "synthetic",
            "reason": "Preserve excerpt",
        },
    )
    assert evidence.status_code == 201, evidence.text
    version += 1
    assigned = api.post(
        f"/api/v1/cases/{case_id}/assignment",
        json={
            "expected_version": version,
            "assignee_id": str(LOCAL_ANALYST_ID),
            "reason": "Analyst owns review",
        },
    )
    assert assigned.status_code == 200 and assigned.json()["owner_handle"] == "local-analyst"
    version += 1
    for state in ("triaging", "investigating", "resolved", "closed"):
        body = {"expected_version": version, "status": state, "reason": f"Analyst selected {state}"}
        if state == "resolved":
            body["disposition"] = "true_positive"
        response = api.post(f"/api/v1/cases/{case_id}/transitions", json=body)
        assert response.status_code == 200, response.text
        version += 1
    history = api.get(f"/api/v1/cases/{case_id}/timeline").json()
    assert history["total"] == version
    assert all(
        event["actor_id"] == str(LOCAL_ANALYST_ID) and event["actor_handle"] == "local-analyst"
        for event in history["items"]
    )
    revision = next(event for event in history["items"] if event["action"] == "note_edited")
    assert revision["before"]["note"]["body"] == original
    assert revision["after"]["note"]["body"] == "Analyst revised note"
    closed_edit = api.patch(
        f"/api/v1/cases/{case_id}",
        json={"expected_version": version, "title": "Blocked", "reason": "Closed"},
    )
    assert closed_edit.status_code == 409 and closed_edit.json()["code"] == "invalid_transition"
    reopened = api.post(
        f"/api/v1/cases/{case_id}/transitions",
        json={"expected_version": version, "status": "investigating", "reason": "New information"},
    )
    assert reopened.status_code == 200 and reopened.json()["disposition"] is None
    assert api.get(f"/api/v1/cases/{case_id}/evidence").json()["items"][0]["snapshot"] == original
    assert api.get(f"/api/v1/alerts/{alert['id']}").json()["cases"][0]["id"] == case_id


def test_write_boundary_rejects_cross_origin_host_csrf_and_actor_injection(api):
    for headers, status, code in (
        ({"Origin": "https://attacker.invalid"}, 403, "invalid_origin"),
        ({"Host": "attacker.invalid"}, 400, "invalid_host"),
        ({"X-ATE-CSRF": ""}, 403, "csrf_invalid"),
        ({"X-ATE-CSRF": b"\xc3\xa9"}, 403, "csrf_invalid"),
    ):
        response = api.post("/api/v1/cases", json={"title": "Blocked"}, headers=headers)
        assert response.status_code == status
        assert response.json()["code"] == code
        assert response.headers["x-correlation-id"] == response.json()["correlation_id"]
        assert response.headers["content-type"].startswith("application/problem+json")
        assert "access-control-allow-origin" not in response.headers
    spoofed = api.post("/api/v1/cases", json={"title": "Blocked", "actor_id": str(uuid4())})
    assert spoofed.status_code == 422 and spoofed.json()["errors"][0]["field"] == "body.actor_id"
    assert api.get("/api/v1/cases").json()["total"] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"provider": "elastic"},
        {"source_ref": "https://example.invalid"},
        {"host": "real.example.com"},
        {"observed_at": "2026-10-28"},
    ],
)
def test_manual_alerts_are_synthetic_and_validated(api, changes):
    response = api.post("/api/v1/alerts", json=alert_input(**changes))
    assert response.status_code == 422
    assert api.get("/api/v1/alerts").json()["total"] == 0


def test_filter_sort_pagination_and_dashboard_are_database_backed(api):
    low = create(api, "100% validated_case", severity="low")
    high = create(api, "High severity case", severity="high")
    create(api, "Medium severity case", severity="medium")
    page = api.get("/api/v1/cases", params={"sort": "severity", "limit": 1, "offset": 0}).json()
    assert page["total"] == 3 and page["items"][0]["id"] == high["id"]
    assert api.get("/api/v1/cases", params={"q": "100%"}).json()["total"] == 1
    assert (
        api.get("/api/v1/cases", params={"q": "validated_"}).json()["items"][0]["id"] == low["id"]
    )
    assert api.get("/api/v1/cases", params={"severity": "critical"}).json()["total"] == 0
    assert api.get("/api/v1/cases", params={"limit": 101}).status_code == 422
    assert api.get("/api/v1/cases", params={"sort": "title; DROP TABLE cases"}).status_code == 422
    dashboard = api.get("/api/v1/dashboard").json()
    assert (
        dashboard["open_cases"]
        == dashboard["total_cases"]
        == dashboard["unassigned_open_cases"]
        == 3
    )
    assert dashboard["severity_counts"] == {"low": 1, "medium": 1, "high": 1, "critical": 0}


def test_concurrent_http_edits_have_one_winner_and_clear_conflict(api):
    case = create(api)

    def edit(title):
        return api.patch(
            f"/api/v1/cases/{case['id']}",
            json={"expected_version": 1, "title": title, "reason": "Concurrent review"},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(edit, ["First edit", "Second edit"]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    failed = next(response for response in responses if response.status_code == 409)
    assert failed.json()["code"] == "version_conflict"
    assert api.get(f"/api/v1/cases/{case['id']}/timeline").json()["total"] == 2


def test_create_and_link_roll_back_together_and_problem_details_hide_inputs(api):
    response = api.post("/api/v1/cases", json={"title": "No orphan", "alert_id": str(uuid4())})
    assert response.status_code == 404
    assert api.get("/api/v1/cases").json()["total"] == 0
    invalid = api.post("/api/v1/cases", json={"title": "x", "severity": "synthetic-private-secret"})
    assert invalid.status_code == 422 and "synthetic-private-secret" not in invalid.text
    too_big = api.post(
        "/api/v1/cases", content="x" * 65537, headers={"Content-Type": "application/json"}
    )
    assert too_big.status_code == 413


def test_commit_failure_cannot_return_success(api, monkeypatch):
    monkeypatch.setattr(CaseService, "_record", lambda *args, **kwargs: None)
    response = api.post("/api/v1/cases", json={"title": "Must not commit without audit"})
    assert response.status_code == 500, response.text
    assert response.json()["code"] == "internal_error"
    assert api.get("/api/v1/cases").json()["total"] == 0


def test_storage_outage_is_a_recoverable_redacted_problem(api):
    @asynccontextmanager
    async def fail():
        raise OperationalError(
            "synthetic-private-query", None, RuntimeError("synthetic-private-password")
        )
        yield

    class BrokenFactory:
        begin = staticmethod(fail)

    api.app.state.sessions = BrokenFactory()
    response = api.get("/api/v1/cases")
    assert response.status_code == 503 and response.json()["code"] == "storage_unavailable"
    assert "private" not in response.text


def test_inactive_local_identity_cannot_read_or_write_business_data(api, database):
    url = (
        database[0].database_url.set(drivername="postgresql").render_as_string(hide_password=False)
    )
    with psycopg.connect(url) as connection:
        connection.execute("UPDATE users SET is_active = false WHERE id = %s", (LOCAL_ANALYST_ID,))
    assert api.get("/api/v1/cases").status_code == 503
    assert api.post("/api/v1/cases", json={"title": "Blocked"}).status_code == 503
    assert api.get("/api/v1/health").status_code == 200


def test_notes_evidence_unlink_and_child_pagination(api):
    case = create(api)
    case_id = case["id"]
    for version in range(1, 4):
        assert (
            api.post(
                f"/api/v1/cases/{case_id}/notes",
                json={"expected_version": version, "body": f"Note {version}"},
            ).status_code
            == 201
        )
    notes = api.get(f"/api/v1/cases/{case_id}/notes", params={"limit": 1, "offset": 1}).json()
    assert notes["total"] == 3 and len(notes["items"]) == 1
    assert api.get(f"/api/v1/cases/{uuid4()}/notes").status_code == 404
    response = api.post(
        f"/api/v1/cases/{case_id}/evidence",
        json={
            "expected_version": 4,
            "provider": "synthetic",
            "provider_scope": "manual",
            "source_event_id": "1",
            "source_ref": "synthetic://event/1",
            "observed_at": "2026-10-28T10:00:00Z",
            "reason": "Pointer only",
        },
    )
    assert response.status_code == 201
    removed = api.request(
        "DELETE",
        f"/api/v1/cases/{case_id}/evidence/{response.json()['subject_id']}",
        json={"expected_version": 5, "reason": "Remove from active investigation"},
    )
    assert removed.status_code == 200
    assert (
        api.get(f"/api/v1/cases/{case_id}/evidence").json()["items"][0]["unlinked_at"] is not None
    )
    assert api.get(f"/api/v1/cases/{case_id}/timeline", params={"limit": 1}).json()["total"] == 6


def test_alert_relationship_changes_and_source_filters_do_not_duplicate_cases(api):
    first, second = create(api, "First relationship"), create(api, "Second relationship")
    alerts = [
        api.post("/api/v1/alerts", json=alert_input(external_alert_id=f"source-{number}")).json()[
            "alert"
        ]
        for number in range(2)
    ]
    for record, version, alert in (
        (first, 1, alerts[0]),
        (first, 2, alerts[1]),
        (second, 1, alerts[0]),
    ):
        response = api.post(
            f"/api/v1/cases/{record['id']}/alerts",
            json={
                "expected_version": version,
                "alert_id": alert["id"],
                "reason": "Synthetic relationship",
            },
        )
        assert response.status_code == 201
    filtered = api.get("/api/v1/cases", params={"provider": "synthetic"}).json()
    assert filtered["total"] == len(filtered["items"]) == 2
    duplicate = api.post(
        f"/api/v1/cases/{first['id']}/alerts",
        json={"expected_version": 3, "alert_id": alerts[0]["id"], "reason": "Already linked"},
    )
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "association_conflict"
    assert api.get(f"/api/v1/cases/{first['id']}").json()["version"] == 3
    for version, alert in ((3, alerts[0]), (4, alerts[1])):
        removed = api.request(
            "DELETE",
            f"/api/v1/cases/{first['id']}/alerts/{alert['id']}",
            json={"expected_version": version, "reason": "Grouping corrected by analyst"},
        )
        assert removed.status_code == 200
    assert api.get("/api/v1/cases", params={"provider": "synthetic"}).json()["total"] == 1
    assert api.get(f"/api/v1/alerts/{alerts[0]['id']}").json()["linked_case_count"] == 1
    assert api.get(f"/api/v1/cases/{first['id']}/alerts").json()["total"] == 0
