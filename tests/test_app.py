from fastapi.testclient import TestClient

from app.main import app


def test_fastapi_starts_and_serves_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_reset_runtime_reports_no_active_workflows():
    with TestClient(app) as client:
        ready = client.get("/ready")
        integrations = client.get("/integrations/health")

    assert ready.status_code == 200
    assert ready.json()["market_scanners_active"] is False
    assert ready.json()["signal_engines_active"] is False
    assert ready.json()["automatic_alerts_active"] is False
    assert integrations.status_code == 200
    assert "checks" in integrations.json()
