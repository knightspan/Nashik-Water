from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def record(**overrides: Any) -> dict[str, Any]:
    """A valid ingest payload (the Pi's data contract)."""
    base: dict[str, Any] = {
        "source": "ramkund",
        "colour": "GREEN",
        "label": "Normal",
        "confidence": 97.0,
        "wqi": 241.6,
        "ph": 7.81,
        "tds": 331.2,
        "turb": 17.8,
        "temp": 24.6,
        "health": "ok",
        "synthetic": False,
        "latency_ms": 12.5,
        "updated": "2026-11-20 13:05:00",
    }
    base.update(overrides)
    if isinstance(base.get("ts"), datetime):
        base["ts"] = base["ts"].isoformat()
    return base


def now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)
