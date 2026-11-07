"""End-to-end check of the Pi engine with the trained model (skipped if not trained yet)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
MODEL_DIR = Path(__file__).resolve().parents[2] / "ml" / "models"
pytestmark = pytest.mark.skipif(not (MODEL_DIR / "random_forest.joblib").exists(), reason="model not trained")


@pytest.fixture(scope="module")
def engine():  # type: ignore[no-untyped-def]
    from edge_ai import EdgeEngine
    from wqm_ml.model import WaterModel

    return EdgeEngine(WaterModel.load(MODEL_DIR))


def _feed(engine, site: str, minutes: int, start: datetime, fn) -> list[dict]:  # type: ignore[no-untyped-def]
    out = []
    for m in range(minutes):
        rec = engine.on_reading(site, fn(m), start + timedelta(minutes=m))
        if rec:
            out.append(rec)
    return out


def test_learning_then_normal_then_contamination(engine) -> None:  # type: ignore[no-untyped-def]
    import random

    rnd = random.Random(1)
    start = datetime(2026, 11, 2, 6, 0, tzinfo=UTC)  # 11:30 IST: no bathing

    def calm(_m: int) -> dict:
        return {"node": "node_01", "ph": 7.8 + rnd.gauss(0, 0.02), "tds": 330 + rnd.gauss(0, 3),
                "turb": 15 + rnd.gauss(0, 0.5), "temp": 24.5 + rnd.gauss(0, 0.05), "temp_ok": 1}  # fmt: skip

    recs = _feed(engine, "ramkund", 180, start, calm)
    assert recs[0]["label"] == "Learning baseline" and recs[0]["colour"] == "GREY"
    tail = recs[-6:]
    assert all(r["colour"] == "GREEN" for r in tail), [r["label"] for r in tail]
    assert all(r["health"] == "ok" and r["ts"].endswith("+00:00") for r in tail)

    def sewage(m: int) -> dict:
        k = min(m / 10, 1.0)
        r = calm(m)
        r.update(ph=r["ph"] - 0.6 * k, tds=r["tds"] + 300 * k, turb=r["turb"] + 50 * k)
        return r

    bad = _feed(engine, "ramkund", 40, start + timedelta(minutes=180), sewage)
    assert any(r["colour"] == "RED" and r["label"] == "Contamination" for r in bad)


def test_stuck_sensor_is_grey(engine) -> None:  # type: ignore[no-untyped-def]
    start = datetime(2026, 11, 2, 6, 0, tzinfo=UTC)
    recs = _feed(
        engine, "tapovan", 60, start, lambda m: {"ph": 7.7, "tds": 420.0, "turb": 22.0 + m * 0.01, "temp": 25.0}
    )
    assert recs[-1]["health"] == "flatline"
    assert recs[-1]["colour"] == "GREY" and recs[-1]["label"] == "Sensor check"


def test_silence_watchdog(engine) -> None:  # type: ignore[no-untyped-def]
    later = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
    recs = engine.silence_check(later, 10)
    assert {r["source"] for r in recs} >= {"ramkund"}
    assert all(r["health"] == "offline" and r["colour"] == "GREY" for r in recs)


def test_outbox_roundtrip(tmp_path: Path) -> None:
    from edge_ai import Outbox

    ob = Outbox(tmp_path / "o.db")
    for i in range(3):
        ob.put({"i": i})
    items = ob.peek(2)
    assert [p["i"] for _, p in items] == [0, 1]
    ob.drop([i for i, _ in items])
    assert ob.size() == 1
