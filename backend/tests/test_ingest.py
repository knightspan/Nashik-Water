"""Ingest validation, idempotency, batch flush and alert de-duplication."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Alert, Reading

from .helpers import now, record


def test_ingest_stores_reading_and_updates_sources(
    client: TestClient, key_headers: dict[str, str]
) -> None:
    res = client.post("/api/ingest", json=record(), headers=key_headers)
    assert res.status_code == 201, res.text
    assert res.json() == {"stored": True, "duplicate": False, "alert_id": None}

    sources = {s["id"]: s for s in client.get("/api/sources").json()}
    assert len(sources) == 7
    ram = sources["ramkund"]
    assert ram["latest"]["colour"] == "GREEN"
    assert ram["latest"]["wqi_band"] == "unfit"
    assert ram["stale"] is False
    assert ram["status_colour"] == "GREEN"
    # No data yet -> stale and GREY.
    assert sources["tapovan"]["latest"] is None
    assert sources["tapovan"]["stale"] is True
    assert sources["tapovan"]["status_colour"] == "GREY"


def test_missing_ts_uses_server_utc_time(
    client: TestClient, key_headers: dict[str, str], db: Session
) -> None:
    before = datetime.now(UTC)
    client.post("/api/ingest", json=record(), headers=key_headers)
    ts = db.scalar(select(Reading.ts).where(Reading.site_id == "ramkund"))
    assert ts is not None
    assert before - timedelta(seconds=5) <= ts <= datetime.now(UTC) + timedelta(seconds=5)


def test_explicit_ts_is_idempotent(client: TestClient, key_headers: dict[str, str]) -> None:
    payload = record(ts=now() - timedelta(minutes=5))
    first = client.post("/api/ingest", json=payload, headers=key_headers).json()
    second = client.post("/api/ingest", json=payload, headers=key_headers).json()
    assert first["stored"] is True
    assert second == {"stored": False, "duplicate": True, "alert_id": None}


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong-key"}])
def test_bad_or_missing_key_is_401(client: TestClient, headers: dict[str, str]) -> None:
    assert client.post("/api/ingest", json=record(), headers=headers).status_code == 401


def test_bad_key_wins_over_bad_body(client: TestClient) -> None:
    res = client.post("/api/ingest", json=record(ph=99), headers={"X-API-Key": "nope"})
    assert res.status_code == 401


def test_unknown_site_is_404(client: TestClient, key_headers: dict[str, str]) -> None:
    res = client.post("/api/ingest", json=record(source="mars_base"), headers=key_headers)
    assert res.status_code == 404


@pytest.mark.parametrize(
    "field,value",
    [
        ("ph", 14.01),
        ("ph", -0.1),
        ("tds", 2000.5),
        ("turb", 3001),
        ("temp", 50.5),
        ("temp", -1),
        ("confidence", 101),
        ("colour", "BLUE"),
        ("label", "Fine"),
        ("health", "dead"),
        ("source", "Bad Id!"),
    ],
)
def test_invalid_values_are_422(
    client: TestClient, key_headers: dict[str, str], field: str, value: object
) -> None:
    res = client.post("/api/ingest", json=record(**{field: value}), headers=key_headers)
    assert res.status_code == 422


def test_range_edges_are_accepted(client: TestClient, key_headers: dict[str, str]) -> None:
    for i, (ph, tds, turb, temp) in enumerate([(0, 0, 0, 0), (14, 2000, 3000, 50)]):
        payload = record(ph=ph, tds=tds, turb=turb, temp=temp, ts=now() - timedelta(minutes=i))
        assert client.post("/api/ingest", json=payload, headers=key_headers).status_code == 201


def test_future_ts_is_422(client: TestClient, key_headers: dict[str, str]) -> None:
    payload = record(ts=now() + timedelta(hours=2))
    assert client.post("/api/ingest", json=payload, headers=key_headers).status_code == 422


def test_offline_record_without_values(client: TestClient, key_headers: dict[str, str]) -> None:
    payload = record(
        ph=None,
        tds=None,
        turb=None,
        temp=None,
        wqi=None,
        colour="GREY",
        label="Sensor check",
        health="offline",
        confidence=0,
    )
    assert client.post("/api/ingest", json=payload, headers=key_headers).status_code == 201


def test_batch_is_idempotent(client: TestClient, key_headers: dict[str, str]) -> None:
    t = now() - timedelta(minutes=30)
    batch = [
        record(ts=t),
        record(ts=t + timedelta(minutes=5)),
        record(source="tapovan", ts=t, synthetic=True),
    ]
    first = client.post("/api/ingest/batch", json=batch, headers=key_headers).json()
    assert first == {"received": 3, "stored": 3, "duplicates": 0, "alerts_created": 0}
    again = client.post("/api/ingest/batch", json=batch, headers=key_headers).json()
    assert again == {"received": 3, "stored": 0, "duplicates": 3, "alerts_created": 0}


def test_batch_with_unknown_site_stores_nothing(
    client: TestClient, key_headers: dict[str, str], db: Session
) -> None:
    batch = [record(ts=now()), record(source="nowhere", ts=now())]
    assert client.post("/api/ingest/batch", json=batch, headers=key_headers).status_code == 404
    assert db.scalar(select(func.count()).select_from(Reading)) == 0


def test_empty_batch_is_422(client: TestClient, key_headers: dict[str, str]) -> None:
    assert client.post("/api/ingest/batch", json=[], headers=key_headers).status_code == 422


def test_red_creates_one_alert_per_30_minutes(
    client: TestClient, key_headers: dict[str, str], db: Session
) -> None:
    t0 = now() - timedelta(hours=2)
    red = {"colour": "RED", "label": "Contamination", "confidence": 91.0}

    def post(minutes: int, **extra: object) -> dict[str, object]:
        payload = record(ts=t0 + timedelta(minutes=minutes), **{**red, **extra})
        return client.post("/api/ingest", json=payload, headers=key_headers).json()

    assert post(0)["alert_id"] is not None
    assert post(10)["alert_id"] is None
    assert post(29)["alert_id"] is None
    assert post(20, colour="GREEN", label="Normal")["alert_id"] is None
    assert post(31)["alert_id"] is not None  # > 30 min after the previous alert
    assert db.scalar(select(func.count()).select_from(Alert)) == 2

    # A duplicate RED record never creates a second alert.
    assert post(0)["duplicate"] is True
    assert db.scalar(select(func.count()).select_from(Alert)) == 2


def test_red_batch_creates_single_alert(client: TestClient, key_headers: dict[str, str]) -> None:
    t0 = now() - timedelta(hours=1)
    batch = [
        record(source="tapovan", colour="RED", label="Contamination", ts=t0 + timedelta(minutes=m))
        for m in range(0, 25, 5)
    ]
    res = client.post("/api/ingest/batch", json=batch, headers=key_headers).json()
    assert res["alerts_created"] == 1
    alerts = client.get("/api/alerts", params={"site": "tapovan"}).json()
    assert len(alerts) == 1
    assert alerts[0]["site_name_mr"] == "तपोवन"
    assert alerts[0]["acknowledged"] is False
    assert client.get("/api/summary").json()["active_alerts"] == 1


def test_ingest_publishes_live_events(
    client: TestClient, key_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.events import broker

    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(broker, "publish", lambda e, d: events.append((e, d)))
    client.post(
        "/api/ingest",
        json=record(colour="RED", label="Contamination"),
        headers=key_headers,
    )
    kinds = [e for e, _ in events]
    assert kinds == ["reading", "alert"]
    assert events[0][1]["id"] == "ramkund"
    assert events[0][1]["status_colour"] == "RED"

    # Old backfill does not announce a "new" latest reading.
    events.clear()
    old = record(ts=now() - timedelta(days=2))
    client.post("/api/ingest", json=old, headers=key_headers)
    assert events == []
