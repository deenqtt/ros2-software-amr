from __future__ import annotations

import pytest

from app.config import Settings


def test_cors_origins_accepts_a_comma_separated_string():
    settings = Settings(cors_origins="http://a.test, http://b.test ")
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_production_refuses_a_wildcard_origin():
    """
    The exact defect the previous backend shipped: allow_origins=["*"] with no
    authentication, on a host-network container next to an open rosbridge.
    """
    settings = Settings(env="production", cors_origins="*")
    with pytest.raises(ValueError, match="refused"):
        settings.validate_for_runtime()


def test_development_tolerates_a_wildcard_origin():
    Settings(env="development", cors_origins="*").validate_for_runtime()


def test_empty_origins_are_refused():
    settings = Settings(cors_origins="")
    with pytest.raises(ValueError, match="empty"):
        settings.validate_for_runtime()


def test_cors_allows_every_method_the_api_serves():
    """
    A method missing here fails only in a browser: curl and TestClient do not
    preflight, so the gap is invisible to everything except the real UI. PUT was
    absent while map assignment used it.
    """
    from starlette.middleware.cors import CORSMiddleware

    from app.main import create_app

    app = create_app(Settings(cors_origins=["http://localhost:3100"], env="development"))
    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    allowed = {method.upper() for method in cors.kwargs["allow_methods"]}

    required: set[str] = set()
    for route in app.routes:
        required |= getattr(route, "methods", None) or set()
    required -= {"HEAD"}

    assert required <= allowed, f"CORS blocks {sorted(required - allowed)}"


def test_a_non_finite_number_is_rejected_not_a_server_error(client):
    """
    FastAPI echoes the offending value back in a validation error, and JSON
    cannot represent NaN — so a request carrying one used to be rejected
    correctly and *then* fail in the response encoder, surfacing as a 500. A
    malformed request must never read as a server fault.
    """
    response = client.post(
        "/api/robots",
        content='{"name": "A", "bridge_url": "ws://h:1", "ros_domain_id": NaN}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]


def _production(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "env": "production",
        "cors_origins": ["https://amr.example.local"],
        "agent_auth": "required",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_refuses_an_insecure_cookie():
    """Plain HTTP in production sends the session cookie and passwords in clear."""
    with pytest.raises(ValueError, match="AMR_ALLOW_INSECURE_HTTP=true"):
        _production(cookie_secure=False).validate_for_runtime()


def test_production_runs_over_https():
    _production(cookie_secure=True).validate_for_runtime()


def test_production_over_plain_http_must_be_chosen_explicitly():
    _production(cookie_secure=False, allow_insecure_http=True).validate_for_runtime()


def test_insecure_http_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("AMR_ALLOW_INSECURE_HTTP", "true")
    assert _production().allow_insecure_http is True


def test_development_does_not_need_https():
    Settings(_env_file=None, env="development").validate_for_runtime()
