"""Weighted arithmetic WQI with BIS IS 10500 limits (identical to backend/app/wqi.py)."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

STANDARDS = {"ph": 8.5, "tds": 500.0, "turb": 5.0}
_INV = {k: 1.0 / v for k, v in STANDARDS.items()}
WEIGHTS = {k: v / sum(_INV.values()) for k, v in _INV.items()}  # 0.368, 0.006, 0.626

ArrayLike = float | npt.NDArray[np.float64]


def wqi(ph: ArrayLike, tds: ArrayLike, turb: ArrayLike) -> ArrayLike:
    ph_a = np.asarray(ph, dtype=float)
    q_ph = np.where(ph_a >= 7.0, 100.0 * (ph_a - 7.0) / 1.5, 100.0 * (7.0 - ph_a) / 0.5)
    out = (
        WEIGHTS["ph"] * q_ph
        + WEIGHTS["tds"] * 100.0 * np.asarray(tds, dtype=float) / 500.0
        + WEIGHTS["turb"] * 100.0 * np.asarray(turb, dtype=float) / 5.0
    )
    return float(out) if np.ndim(out) == 0 else out
