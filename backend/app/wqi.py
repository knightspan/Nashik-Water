"""Weighted arithmetic Water Quality Index (BIS IS 10500 limits).

Same formula as the Raspberry Pi (edge/edge_ai.py), the simulator and the ML pipeline:
    Wi ∝ 1/Si  (Si: pH 8.5, TDS 500 mg/L, turbidity 5 NTU)  ->  0.368, 0.006, 0.626
    Q_pH  = 100·(pH-7)/1.5 if pH ≥ 7 else 100·(7-pH)/0.5
    Q_TDS = 100·TDS/500,  Q_turb = 100·NTU/5
    WQI   = Σ Wi·Qi
"""

from __future__ import annotations

STANDARDS = {"ph": 8.5, "tds": 500.0, "turb": 5.0}
_INV = {k: 1.0 / v for k, v in STANDARDS.items()}
WEIGHTS = {k: v / sum(_INV.values()) for k, v in _INV.items()}

# Upper bound of each band (inclusive); anything above the last is "unfit".
BANDS: list[tuple[str, float]] = [
    ("excellent", 25.0),
    ("good", 50.0),
    ("poor", 75.0),
    ("very_poor", 100.0),
]
BAND_NAMES = [b for b, _ in BANDS] + ["unfit"]


def q_ph(ph: float) -> float:
    return 100.0 * (ph - 7.0) / 1.5 if ph >= 7.0 else 100.0 * (7.0 - ph) / 0.5


def compute_wqi(ph: float, tds: float, turb: float) -> float:
    return (
        WEIGHTS["ph"] * q_ph(ph)
        + WEIGHTS["tds"] * 100.0 * tds / 500.0
        + WEIGHTS["turb"] * 100.0 * turb / 5.0
    )


def wqi_band(wqi: float | None) -> str | None:
    if wqi is None:
        return None
    for name, upper in BANDS:
        if wqi <= upper:
            return name
    return "unfit"
