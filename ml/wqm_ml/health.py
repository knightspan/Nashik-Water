"""Sensor-health checks on recent 1-minute readings.

Returns one of the web API's health values: ok | offline | flatline | out_of_range.
Rules, not a model: they are exact, explainable and need no training data, and they run
before the classifier so a broken probe can never turn a site RED.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .features import PARAMS

FLAT_WINDOW = 30  # minutes of identical values that mean "stuck sensor"
FLAT_MIN = 20  # readings needed before flatline can be judged
OFFLINE_RECENT = 5  # look at the last 5 minutes...
OFFLINE_MISSING = 3  # ...offline if at least 3 of them have no data
PH_PLAUSIBLE = (2.0, 12.0)  # natural waters; outside this the probe is dry/broken
RAIL = {"tds": 1990.0, "turb": 2990.0}  # ADC rail / sensor saturation
TEMP_PLAUSIBLE = (0.5, 45.0)  # DS18B20 85 °C reset value and 0 °C disconnects are rejected


def sensor_health(rows: pd.DataFrame | list[dict[str, float]]) -> str:
    """rows: recent 1-minute readings of ONE site, oldest first (columns PARAMS)."""
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows, columns=PARAMS)
    if df.empty:
        return "offline"
    df = df[PARAMS].astype(float)
    recent = df.tail(OFFLINE_RECENT)
    if int(recent.isna().all(axis=1).sum()) >= min(OFFLINE_MISSING, len(recent)):
        return "offline"

    last30 = df[["ph", "tds", "turb"]].tail(FLAT_WINDOW).dropna()
    if len(last30) >= FLAT_MIN:
        for p in ("ph", "tds", "turb"):
            col = last30[p]
            # Constant value = stuck. Turbidity resting at exactly 0 in clear water is fine.
            if col.nunique() == 1 and not (p == "turb" and col.iloc[0] <= 0.0):
                return "flatline"

    last = recent.ffill().iloc[-1]
    if not PH_PLAUSIBLE[0] <= last["ph"] <= PH_PLAUSIBLE[1]:
        return "out_of_range"
    if last["tds"] >= RAIL["tds"] or last["turb"] >= RAIL["turb"]:
        return "out_of_range"
    if not TEMP_PLAUSIBLE[0] <= last["temp"] <= TEMP_PLAUSIBLE[1]:
        return "out_of_range"
    return "ok"


def health_series(minutes: pd.DataFrame) -> np.ndarray:
    """Vectorised sensor_health for every minute of ONE site (used to evaluate the rules)."""
    df = minutes[PARAMS].astype(float).reset_index(drop=True)
    allnan = df.isna().all(axis=1).astype(int)
    offline = allnan.rolling(OFFLINE_RECENT, min_periods=1).sum() >= OFFLINE_MISSING

    flat = pd.Series(False, index=df.index)
    for p in ("ph", "tds", "turb"):
        col = df[p]
        roll = col.rolling(FLAT_WINDOW, min_periods=FLAT_MIN)
        stuck = (roll.max() - roll.min() == 0) & ~((p == "turb") & (col <= 0))
        flat |= stuck.fillna(False)

    last = df.ffill()
    oor = (
        ~last["ph"].between(*PH_PLAUSIBLE)
        | (last["tds"] >= RAIL["tds"])
        | (last["turb"] >= RAIL["turb"])
        | ~last["temp"].between(*TEMP_PLAUSIBLE)
    )
    out = np.where(offline, "offline", np.where(flat, "flatline", np.where(oor, "out_of_range", "ok")))
    return out
