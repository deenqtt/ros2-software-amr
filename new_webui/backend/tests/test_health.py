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
    assert "env" not in body


def test_ready_leaks_nothing_internal(client):
    body = client.get("/ready").json()
    assert set(body) == {"status", "schema_version"}


def test_ready_failure_is_generic(client, monkeypatch):
    import sqlite3

    from app.api import health

    class Broken:
        def execute(self, *_a):
            raise sqlite3.OperationalError("no such table: /secret/path.db")

    from app.api.deps import get_connection

    client.app.dependency_overrides[get_connection] = lambda: Broken()
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "detail": "not ready"}
    assert "secret" not in response.text
    assert health.log is not None


def test_docs_are_served_in_development(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 200


def test_docs_are_absent_in_production(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    prod = settings.model_copy(update={"env": "production", "cookie_secure": True})
    with TestClient(create_app(prod)) as c:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert c.get(path).status_code == 404
