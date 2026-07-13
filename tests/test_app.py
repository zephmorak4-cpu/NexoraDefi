from fastapi.testclient import TestClient

from app.main import app


def test_fastapi_starts_and_serves_health():
    with TestClient(app) as client:
        response = client.get("/health")
        live = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert live.status_code == 200
    assert live.json()["status"] == "alive"
    assert live.json()["service"] == "solana-spot-momentum-engine"


def test_spot_runtime_reports_fail_safe_readiness():
    with TestClient(app) as client:
        ready = client.get("/ready")
        health_ready = client.get("/health/ready")
        health_details = client.get("/health/details")
        integrations = client.get("/integrations/health")

    assert ready.status_code in {200, 503}
    assert health_ready.status_code in {200, 503}
    assert health_details.status_code in {200, 503}
    assert ready.json()["runtime"] == "spot_momentum_paper_trading"
    assert health_details.json()["safety"]["live_buying"] == "NOT_IMPLEMENTED"
    assert ready.json()["market_scanners_active"] is True
    assert ready.json()["signal_engines_active"] is True
    assert "missing_capabilities" in ready.json()
    assert integrations.status_code == 200
    assert "checks" in integrations.json()
