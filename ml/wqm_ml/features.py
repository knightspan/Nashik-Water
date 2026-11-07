"""5-minute windows and model features. Used identically in training and on the Pi.

Only past data is used (no centred filters), so the Pi can compute the same values live:
    1-min readings ─► 5-min window = median of ≥3 valid readings ─► features
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from .wqi import wqi

PARAMS = ["ph", "tds", "turb", "temp"]
WINDOW = "5min"
MIN_VALID = 3  # valid 1-min readings needed for a window
FFILL_LIMIT = 3  # windows a short gap may be bridged for (15 min)
MIN_HISTORY = 30  # windows needed before classifying (2.5 h) — "Learning baseline" until then
HISTORY = 96  # windows the Pi keeps per site (8 h)
TZ = "Asia/Kolkata"

# Small constants that stop relative deviations exploding near zero.
DEV_EPS = {"ph": 0.1, "tds": 10.0, "turb": 1.0}

FEATURES = [
    "ph", "tds", "turb", "temp", "wqi",
    "d1_ph", "d1_tds", "d1_turb",
    "d3_ph", "d3_tds", "d3_turb", "d3_temp",
    "sd_ph", "sd_tds", "sd_turb", "sd_temp",
    "dev_ph", "dev_tds", "dev_turb",
    "h_sin", "h_cos",
    "rel_ph", "rel_tds", "rel_turb",
]  # fmt: skip

# The 6 features the Arduino UNO can compute for its on-board decision tree.
ARDUINO_FEATURES = ["rel_ph", "rel_tds", "rel_turb", "d3_tds", "d3_turb", "d3_ph"]

Baseline = Mapping[str, float]


def aggregate_window(rows: np.ndarray) -> np.ndarray:
    """rows: (k, 4) array of 1-min readings in PARAMS order -> (4,) medians (NaN if too few)."""
    rows = np.asarray(rows, dtype=float)
    valid = (~np.isnan(rows)).sum(axis=0)
    with np.errstate(all="ignore"):
        med = np.nanmedian(rows, axis=0) if len(rows) else np.full(len(PARAMS), np.nan)
    med = np.where(valid >= MIN_VALID, med, np.nan)
    return med


def to_windows(minutes: pd.DataFrame) -> pd.DataFrame:
    """1-minute rows of ONE site (columns ts + PARAMS [+ prio/fault]) -> 5-minute windows."""
    g = minutes.set_index("ts").sort_index()
    r = g[PARAMS].resample(WINDOW)
    med = r.median()
    med[r.count() < MIN_VALID] = np.nan
    out = med.ffill(limit=FFILL_LIMIT)
    if "prio" in g:
        # Label = highest-priority event present in at least MIN_VALID of the minutes.
        counts = pd.get_dummies(g["prio"]).resample(WINDOW).sum()
        label = pd.Series(0, index=counts.index)
        for p in sorted(counts.columns):
            label[counts[p] >= MIN_VALID] = p
        out["prio"] = label
    return out.reset_index()


def site_baseline(windows: pd.DataFrame, days: int = 7) -> dict[str, float]:
    """Unsupervised "normal" for a site: median of its first `days` days of windows."""
    w = windows.dropna(subset=["ph", "tds", "turb"])
    if w.empty:
        raise ValueError("no valid windows to learn a baseline from")
    first = w[w["ts"] < w["ts"].iloc[0] + pd.Timedelta(days=days)]
    return {p: float(first[p].median()) for p in ("ph", "tds", "turb")}


def add_features(windows: pd.DataFrame, baseline: Baseline) -> pd.DataFrame:
    """Add FEATURES columns to the 5-minute windows of ONE site (sorted by time)."""
    g = windows.sort_values("ts").copy()
    g["wqi"] = wqi(g["ph"], g["tds"], g["turb"])
    for p in ("ph", "tds", "turb"):
        g[f"d1_{p}"] = g[p].diff(1)
    for p in PARAMS:
        g[f"d3_{p}"] = g[p].diff(3)
        g[f"sd_{p}"] = g[p].rolling(6, min_periods=3).std()
    for p, eps in DEV_EPS.items():
        base = g[p].shift(6).rolling(72, min_periods=24).median()  # past 6 h, skipping last 30 min
        g[f"dev_{p}"] = (g[p] - base) / (base.abs() + eps)
    ts = pd.to_datetime(g["ts"])
    ts = ts.dt.tz_convert(TZ) if ts.dt.tz is not None else ts.dt.tz_localize(TZ)
    h = ts.dt.hour + ts.dt.minute / 60.0
    g["h_sin"] = np.sin(2 * np.pi * h / 24)
    g["h_cos"] = np.cos(2 * np.pi * h / 24)
    g["rel_ph"] = g["ph"] - baseline["ph"]
    g["rel_tds"] = g["tds"] / max(baseline["tds"], 1.0)
    g["rel_turb"] = (g["turb"] + 0.5) / (baseline["turb"] + 0.5)
    return g


def latest_features(windows: Sequence[Mapping[str, object]] | pd.DataFrame, baseline: Baseline) -> pd.DataFrame | None:
    """Features for the newest window, or None while the history is too short / invalid."""
    df = windows if isinstance(windows, pd.DataFrame) else pd.DataFrame(list(windows))
    if len(df) < MIN_HISTORY:
        return None
    df = df.copy()
    df[PARAMS] = df[PARAMS].ffill(limit=FFILL_LIMIT)
    x = add_features(df, baseline)[FEATURES].iloc[[-1]]
    if x.isna().any(axis=None):
        return None
    return x
