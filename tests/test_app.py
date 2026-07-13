from fastapi.testclient import TestClient

from app.main import app


def test_fastapi_starts_and_serves_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_spot_runtime_reports_fail_safe_readiness():
    with TestClient(app) as client:
        ready = client.get("/ready")
        integrations = client.get("/integrations/health")

    assert ready.status_code in {200, 503}
    assert ready.json()["runtime"] == "spot_momentum_paper_trading"
    assert ready.json()["market_scanners_active"] is True
    assert ready.json()["signal_engines_active"] is True
    assert "missing_capabilities" in ready.json()
    assert integrations.status_code == 200
    assert "checks" in integrations.json()
