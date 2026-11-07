"""Downsampling, statistics, CSV export and retention."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Reading, ReadingHourly
from app.retention import run_retention

from .helpers import now, record


def _post_series(
    client: TestClient, headers: dict[str, str], site: str, start: datetime, n: int, step_min: int
) -> None:
    rows = [record(source=site, ts=start + timedelta(minutes=i * step_min)) for i in range(n)]
    for i in range(0, len(rows), 1000):
        res = client.post("/api/ingest/batch", json=rows[i : i + 1000], headers=headers)
        assert res.status_code == 201, res.text


def test_downsampling_resolution(client: TestClient, key_headers: dict[str, str]) -> None:
    # 10 days of 5-minute readings ending now, starting on the hour so buckets are full.
    start = now().replace(minute=0, second=0) - timedelta(days=10)
    _post_series(client, key_headers, "someshwar", start, 10 * 288, 5)

    raw = client.get("/api/sources/someshwar/readings", params={"hours": 24}).json()
    assert raw["resolution"] == "raw"
    assert 280 <= len(raw["points"]) <= 300
    assert all(p["n"] == 1 for p in raw["points"])

    week = client.get("/api/sources/someshwar/readings", params={"hours": 168}).json()
    assert week["resolution"] == "15min"
    assert 7 * 96 - 8 <= len(week["points"]) <= 7 * 96 + 1
    assert max(p["n"] for p in week["points"]) == 3  # three 5-min readings per bucket

    month = client.get("/api/sources/someshwar/readings", params={"hours": 720}).json()
    assert month["resolution"] == "1h"
    assert 10 * 24 - 2 <= len(month["points"]) <= 10 * 24 + 1
    assert max(p["n"] for p in month["points"]) == 12
    assert month["points"][0]["ts"] < month["points"][-1]["ts"]


def test_bucket_colour_is_worst_in_bucket(client: TestClient, key_headers: dict[str, str]) -> None:
    t = now().replace(minute=0, second=0) - timedelta(hours=3)
    rows = [
        record(source="nandini", ts=t, colour="GREEN"),
        record(source="nandini", ts=t + timedelta(minutes=5), colour="RED", label="Contamination"),
        record(source="nandini", ts=t + timedelta(minutes=10), colour="AMBER"),
    ]
    client.post("/api/ingest/batch", json=rows, headers=key_headers)
    week = client.get("/api/sources/nandini/readings", params={"hours": 48}).json()
    assert [p["colour"] for p in week["points"]] == ["RED"]


def test_readings_unknown_site_404(client: TestClient) -> None:
    assert client.get("/api/sources/nope/readings").status_code == 404
    assert client.get("/api/sources/nope").status_code == 404


def test_hours_out_of_range_422(client: TestClient) -> None:
    assert client.get("/api/sources/ramkund/readings", params={"hours": 0}).status_code == 422


def test_stats(client: TestClient, key_headers: dict[str, str]) -> None:
    t = now() - timedelta(hours=5)
    vals = [(7.0, 100.0, 1.0, "GREEN"), (7.5, 200.0, 2.0, "GREEN"), (8.0, 600.0, 30.0, "RED")]
    rows = [
        record(
            source="kushavart",
            ts=t + timedelta(minutes=i * 5),
            ph=ph,
            tds=tds,
            turb=turb,
            colour=c,
            wqi=w,
        )
        for i, ((ph, tds, turb, c), w) in enumerate(zip(vals, [10.0, 40.0, 400.0], strict=True))
    ]
    client.post("/api/ingest/batch", json=rows, headers=key_headers)
    s = client.get("/api/sources/kushavart/stats", params={"days": 7}).json()
    assert s["count"] == 3
    assert s["params"]["ph"] == {"min": 7.0, "max": 8.0, "mean": 7.5, "median": 7.5}
    assert s["params"]["tds"]["median"] == 200.0
    assert s["colours"]["GREEN"] == 66.7
    assert s["colours"]["RED"] == 33.3
    assert s["wqi_bands"]["excellent"] == 33.3
    assert s["wqi_bands"]["good"] == 33.3
    assert s["wqi_bands"]["unfit"] == 33.3


def test_csv_export(client: TestClient, key_headers: dict[str, str]) -> None:
    t = now() - timedelta(hours=1)
    rows = [record(source="tapovan", ts=t + timedelta(minutes=i), synthetic=True) for i in range(5)]
    client.post("/api/ingest/batch", json=rows, headers=key_headers)
    res = client.get("/api/export/tapovan.csv", params={"days": 1})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]
    lines = res.text.strip().splitlines()
    assert lines[0].startswith("# ") and "SIMULATED" in lines[0]
    assert lines[1].startswith("ts,site_id,ph")
    assert len(lines) == 2 + 5


def test_summary(client: TestClient, key_headers: dict[str, str]) -> None:
    client.post("/api/ingest", json=record(), headers=key_headers)
    client.post(
        "/api/ingest",
        json=record(source="tapovan", colour="AMBER", label="Natural change"),
        headers=key_headers,
    )
    s = client.get("/api/summary").json()
    assert s["sites"] == 7
    assert s["colours"] == {"GREEN": 1, "AMBER": 1, "RED": 0, "GREY": 5}
    assert s["stale_sites"] == 5
    assert s["last_update"] is not None


def test_retention_rolls_up_then_prunes(db: Session) -> None:
    old = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(days=100)
    recent = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=5)
    for base, colour in ((old, "RED"), (recent, "GREEN")):
        for i in range(12):
            db.add(
                Reading(
                    site_id="gangapur_dam",
                    ts=base + timedelta(minutes=5 * i),
                    ph=7.0 + i * 0.1,
                    tds=100,
                    turb=2,
                    temp=24,
                    wqi=10,
                    label="Normal",
                    colour=colour,
                    health="ok",
                )
            )
    db.flush()

    res = run_retention(db)
    assert not res.skipped
    assert res.readings_deleted == 12
    remaining = db.scalar(select(func.count()).select_from(Reading))
    assert remaining == 12

    archived = db.scalar(
        select(ReadingHourly).where(
            ReadingHourly.site_id == "gangapur_dam", ReadingHourly.hour == old
        )
    )
    assert archived is not None
    assert archived.n == 12 and archived.n_red == 12
    assert abs(archived.ph_mean - 7.55) < 1e-9
    assert archived.ph_min == 7.0
    # The recent hour is aggregated too.
    assert (
        db.scalar(
            select(ReadingHourly.n).where(
                ReadingHourly.site_id == "gangapur_dam", ReadingHourly.hour == recent
            )
        )
        == 12
    )

    # Running again is safe (idempotent upsert, nothing left to prune).
    again = run_retention(db)
    assert again.readings_deleted == 0


def test_long_range_uses_hourly_archive(
    client: TestClient, db: Session, key_headers: dict[str, str]
) -> None:
    old = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(days=120)
    db.add(ReadingHourly(site_id="ugamsthan", hour=old, n=12, ph_mean=7.3, wqi_mean=30, n_amber=3))
    db.flush()
    client.post(
        "/api/ingest",
        json=record(source="ugamsthan", ts=now() - timedelta(hours=2)),
        headers=key_headers,
    )
    res = client.get("/api/sources/ugamsthan/readings", params={"hours": 24 * 150}).json()
    assert res["resolution"] == "1h"
    assert res["points"][0]["ph"] == 7.3
    assert res["points"][0]["colour"] == "AMBER"
    assert len(res["points"]) == 2
