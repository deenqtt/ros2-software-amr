from __future__ import annotations


def test_health_is_liveness_only(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reports_the_applied_schema_version(client):
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    # Readiness that does not actually touch the schema is not readiness.
    assert body["schema_version"] >= 1
    assert body["env"] == "development"
