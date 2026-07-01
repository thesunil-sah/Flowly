from fastapi.testclient import TestClient

from app.main import app


def test_health_ok() -> None:
    """GET /health returns 200 without any database running."""
    client = TestClient(app)
    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "environment" in body
    assert body["version"] == "0.1.0"
