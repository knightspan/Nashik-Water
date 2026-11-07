"""JWT auth, admin endpoints, audit log, key rotation, rate limiting, SSE broker."""

import asyncio
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_token, hash_password
from app.models import User

from .helpers import now, record

ADMIN = {"email": "admin@test.local", "password": "test-admin-password"}


def test_login_and_me(client: TestClient) -> None:
    res = client.post("/api/auth/login", json=ADMIN)
    assert res.status_code == 200
    tokens = res.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == 30 * 60
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "admin@test.local"
    assert me.json()["role"] == "admin"


def test_login_is_case_insensitive_on_email(client: TestClient) -> None:
    res = client.post("/api/auth/login", json={**ADMIN, "email": "ADMIN@Test.Local"})
    assert res.status_code == 200


def test_wrong_password_401(client: TestClient) -> None:
    assert client.post("/api/auth/login", json={**ADMIN, "password": "nope"}).status_code == 401
    assert (
        client.post("/api/auth/login", json={"email": "x@y.z", "password": "nope"}).status_code
        == 401
    )


def test_refresh_flow_and_token_types(client: TestClient) -> None:
    tokens = client.post("/api/auth/login", json=ADMIN).json()
    # A refresh token cannot be used as an access token, and vice versa.
    bad = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert bad.status_code == 401
    assert (
        client.post("/api/auth/refresh", json={"refresh_token": tokens["access_token"]}).status_code
        == 401
    )
    new = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert new.status_code == 200
    assert new.json()["access_token"] != tokens["access_token"]


def test_expired_token_401(client: TestClient, db: Session) -> None:
    s = get_settings()
    user = db.query(User).filter_by(email="admin@test.local").one()
    expired = create_token(
        user.id,
        "admin",
        "access",
        s.jwt_secret.get_secret_value(),
        "HS256",
        timedelta(seconds=-5),
    )
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert res.status_code == 401


def test_admin_requires_auth_and_role(client: TestClient, db: Session) -> None:
    assert client.get("/api/admin/sites").status_code == 401
    db.add(
        User(
            email="viewer@test.local", password_hash=hash_password("viewer-pass-123"), role="viewer"
        )
    )
    db.flush()
    tok = client.post(
        "/api/auth/login", json={"email": "viewer@test.local", "password": "viewer-pass-123"}
    ).json()["access_token"]
    assert (
        client.get("/api/admin/sites", headers={"Authorization": f"Bearer {tok}"}).status_code
        == 403
    )


def test_site_crud(client: TestClient, admin_headers: dict[str, str]) -> None:
    new = {
        "id": "panchavati_test",
        "name_en": "Test site",
        "name_mr": "चाचणी",
        "kind": "river",
        "lat": 20.0,
        "lon": 73.8,
        "simulated": True,
    }
    assert client.post("/api/admin/sites", json=new, headers=admin_headers).status_code == 201
    assert client.post("/api/admin/sites", json=new, headers=admin_headers).status_code == 409
    assert len(client.get("/api/sources").json()) == 8

    upd = client.put(
        "/api/admin/sites/panchavati_test",
        json={"lat": 20.01, "description_en": "Edited"},
        headers=admin_headers,
    )
    assert upd.status_code == 200
    assert upd.json()["lat"] == 20.01 and upd.json()["description_en"] == "Edited"

    bad = client.put("/api/admin/sites/panchavati_test", json={"lat": 95}, headers=admin_headers)
    assert bad.status_code == 422

    assert (
        client.delete("/api/admin/sites/panchavati_test", headers=admin_headers).status_code == 200
    )
    ids = [s["id"] for s in client.get("/api/sources").json()]
    assert "panchavati_test" not in ids
    all_sites = client.get("/api/admin/sites", headers=admin_headers).json()
    assert any(s["id"] == "panchavati_test" and not s["active"] for s in all_sites)

    actions = [a["action"] for a in client.get("/api/admin/audit", headers=admin_headers).json()]
    assert {"site.create", "site.update", "site.deactivate", "auth.login"} <= set(actions)


def test_acknowledge_alert(
    client: TestClient, admin_headers: dict[str, str], key_headers: dict[str, str]
) -> None:
    alert_id = client.post(
        "/api/ingest", json=record(colour="RED", label="Contamination"), headers=key_headers
    ).json()["alert_id"]
    res = client.post(
        f"/api/admin/alerts/{alert_id}/ack", json={"note": "Checked on site"}, headers=admin_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body["acknowledged"] is True
    assert body["acknowledged_by"] == "admin@test.local"
    assert body["note"] == "Checked on site"
    assert client.get("/api/summary").json()["active_alerts"] == 0
    assert client.post("/api/admin/alerts/999999/ack", headers=admin_headers).status_code == 404


def test_rotate_api_key(
    client: TestClient, admin_headers: dict[str, str], key_headers: dict[str, str]
) -> None:
    res = client.post("/api/admin/apikeys/rotate", json={"name": "pi-2026"}, headers=admin_headers)
    assert res.status_code == 201
    body = res.json()
    assert body["revoked"] == 1
    assert body["key"].startswith("nwq_")
    assert body["api_key"]["prefix"] == body["key"][:10]

    assert client.post("/api/ingest", json=record(), headers=key_headers).status_code == 401
    new_headers = {"X-API-Key": body["key"]}
    assert client.post("/api/ingest", json=record(), headers=new_headers).status_code == 201

    keys = client.get("/api/admin/apikeys", headers=admin_headers).json()
    assert sum(k["active"] for k in keys) == 1
    assert all("key_hash" not in k for k in keys)


def test_ingest_health(
    client: TestClient, admin_headers: dict[str, str], key_headers: dict[str, str]
) -> None:
    batch = [record(ts=now() - timedelta(minutes=i)) for i in range(4)]
    client.post("/api/ingest/batch", json=batch, headers=key_headers)
    res = client.get("/api/admin/ingest-health", headers=admin_headers).json()
    ram = next(s for s in res["sites"] if s["site_id"] == "ramkund")
    assert ram["messages_last_hour"] == 4
    assert len(ram["hourly"]) == 24 and ram["hourly"][-1] == 4
    assert ram["last_received_at"] is not None


def test_rate_limit_public(client: TestClient) -> None:
    from app.ratelimit import limiter

    limiter.reset()
    limiter.enabled = True
    try:
        codes = [client.get("/api/summary").status_code for _ in range(61)]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codes[:60] == [200] * 60
    assert codes[60] == 429


def test_broker_fanout_and_backpressure() -> None:
    from app.events import Broker

    async def scenario() -> list[str]:
        b = Broker(queue_size=2)
        b.bind(asyncio.get_running_loop())
        async with b.subscribe() as q:
            for i in range(3):
                b.publish("reading", {"i": i})
            await asyncio.sleep(0)
            got = [q.get_nowait()[1] for _ in range(q.qsize())]
        assert b.subscriber_count == 0
        return got

    # Oldest event is dropped when a slow client's queue is full.
    assert asyncio.run(scenario()) == ['{"i": 1}', '{"i": 2}']


def test_cors_allows_frontend_origin(client: TestClient) -> None:
    res = client.options(
        "/api/sources",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"
    evil = client.options(
        "/api/sources",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in evil.headers


def test_sse_events_encode() -> None:
    """Every event the stream yields must be encodable by sse-starlette."""
    from sse_starlette.sse import ServerSentEvent

    from app.events import Broker
    from app.routers.stream import sse_events

    async def scenario() -> list[bytes]:
        b = Broker()
        b.bind(asyncio.get_running_loop())
        gen = sse_events(b)
        hello = await gen.__anext__()
        b.publish("reading", {"id": "ramkund", "status_colour": "RED"})
        reading = await asyncio.wait_for(gen.__anext__(), 1)
        await gen.aclose()
        return [ServerSentEvent(**hello).encode(), ServerSentEvent(**reading).encode()]

    hello, reading = asyncio.run(scenario())
    assert b"event: hello" in hello and b"retry: 5000" in hello
    assert b"event: reading" in reading and b'"status_colour": "RED"' in reading
