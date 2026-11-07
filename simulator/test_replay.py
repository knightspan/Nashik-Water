"""pytest simulator/ -- behaviour checks for the virtual nodes."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest

from replay import SiteSim, backfill, wqi


def test_wqi_matches_api_formula() -> None:
    assert wqi(8.5, 500, 5) == pytest.approx(100)
    assert wqi(7.0, 0, 0) == pytest.approx(0)
    assert 240 < wqi(7.81, 331.2, 17.8) < 246


def _day(site: str, seed: int = 1) -> list[dict]:
    sim = SiteSim(site, random.Random(seed))
    start = datetime(2026, 11, 2, 0, 0, tzinfo=UTC) - timedelta(hours=5, minutes=30)  # IST midnight
    return [sim.step(start + timedelta(minutes=5 * i), 5, spontaneous=False) for i in range(288)]


def test_records_fit_the_ingest_contract() -> None:
    for r in _day("nandini"):
        assert 0 <= r["ph"] <= 14 and 0 <= r["tds"] <= 2000
        assert 0 <= r["turb"] <= 3000 and 0 <= r["temp"] <= 50
        assert r["colour"] in {"GREEN", "AMBER", "RED", "GREY"}
        assert r["synthetic"] is True and r["health"] == "ok"


def test_values_stay_near_baseline() -> None:
    recs = _day("ugamsthan")
    tds = sorted(r["tds"] for r in recs)
    assert 80 < tds[len(tds) // 2] < 140


def test_morning_bathing_is_amber_at_ramkund_only() -> None:
    for site, expect_amber in (("ramkund", True), ("tapovan", False)):
        recs = _day(site)
        morning = [r for i, r in enumerate(recs) if 7 * 12 <= i < 9 * 12]  # 07:00-09:00 IST
        night = [r for i, r in enumerate(recs) if i < 5 * 12]
        assert all(r["colour"] == ("AMBER" if expect_amber else "GREEN") for r in morning)
        assert all(r["colour"] == "GREEN" for r in night)


def test_contamination_event_turns_red_then_recovers() -> None:
    sim = SiteSim("tapovan", random.Random(3))
    t0 = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
    base = sim.step(t0, 1, spontaneous=False)
    sim.add_event("contamination", t0, minutes=60)
    during = [sim.step(t0 + timedelta(minutes=m), 1, spontaneous=False) for m in range(10, 40)]
    assert all(r["colour"] == "RED" and r["label"] == "Contamination" for r in during)
    assert min(r["turb"] for r in during) > base["turb"] + 10
    assert max(r["ph"] for r in during) < base["ph"]
    after = sim.step(t0 + timedelta(minutes=200), 1, spontaneous=False)
    assert after["colour"] == "GREEN"


def test_backfill_spacing() -> None:
    sims = {s: SiteSim(s, random.Random(1)) for s in ("tapovan", "nandini")}
    now = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
    recs = backfill(sims, hours=2, step_min=5, now=now)
    assert len(recs) == 2 * 24
    assert len({(r["source"], r["ts"]) for r in recs}) == len(recs)


def test_backfill_resumes_after_latest_reading() -> None:
    sims = {s: SiteSim(s, random.Random(1)) for s in ("tapovan", "nandini")}
    now = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
    recs = backfill(sims, hours=2, step_min=5, now=now, latest={"tapovan": now - timedelta(minutes=30)})
    assert sum(r["source"] == "tapovan" for r in recs) == 5  # 11:35 ... 11:55
    assert sum(r["source"] == "nandini" for r in recs) == 24


def test_demo_event_is_red_immediately() -> None:
    sim = SiteSim("tapovan", random.Random(4))
    t0 = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
    sim.add_event("contamination", t0, minutes=45, immediate=True)
    assert len(sim.events) == 1
    assert sim.step(t0, 1, spontaneous=False)["colour"] == "RED"
