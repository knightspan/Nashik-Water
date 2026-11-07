from fastapi.testclient import TestClient


def test_health_reports_database_ok(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["database"] == "ok"


def test_openapi_docs_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    for p in [
        "/api/sources",
        "/api/sources/{site_id}/readings",
        "/api/sources/{site_id}/stats",
        "/api/alerts",
        "/api/summary",
        "/api/stream",
        "/api/export/{site_id}.csv",
        "/api/ingest",
        "/api/ingest/batch",
        "/api/auth/login",
        "/api/auth/refresh",
        "/api/auth/me",
        "/api/admin/sites",
        "/api/admin/alerts/{alert_id}/ack",
        "/api/admin/apikeys/rotate",
        "/api/admin/audit",
    ]:
        assert p in paths, p


def test_security_headers(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.headers["x-content-type-options"] == "nosniff"
