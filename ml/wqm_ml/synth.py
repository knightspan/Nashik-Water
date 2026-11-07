"""Labelled synthetic 1-minute telemetry for the 7 sites (training data).

Adapted from WQM_code/pi/synth_water.py. Change from the original: an event's label now
covers only the minutes when its effect is actually present in the water (signal ≥ 15 %
of its peak), instead of a fixed 2-hour tail after the event. Windows where the water
has already returned to normal are no longer labelled "Contamination", so the model is
trained and scored on what the sensors can physically see.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import lfilter

from .sites import NOISE, RANGES, SITES
from .wqi import wqi

EVENT_PRIO = {"normal": 0, "rain": 1, "bathing": 2, "contamination": 4}
LABEL_THRESHOLD = 0.15  # fraction of an event's peak effect that counts as "present"


def ou(rng: np.random.Generator, n: int, sigma: float, tau_min: float) -> np.ndarray:
    """Ornstein-Uhlenbeck noise: slow, mean-reverting natural wandering."""
    a = np.exp(-1.0 / tau_min)
    e = rng.normal(0, sigma * np.sqrt(1 - a * a), n)
    return lfilter([1.0], [1.0, -a], e)


def shape(n: int, t0: int, rise: float, hold: float, tau: float) -> np.ndarray:
    """0→1 linear rise, flat hold, exponential decay."""
    y = np.zeros(n)
    t = np.arange(n) - t0
    rise = max(rise, 1)
    up = (t >= 0) & (t < rise)
    y[up] = t[up] / rise
    y[(t >= rise) & (t < rise + hold)] = 1.0
    down = t >= rise + hold
    y[down] = np.exp(-(t[down] - rise - hold) / tau)
    return y


def gen_site(
    key: str,
    cfg: dict[str, Any],
    start: str,
    days: int,
    rng: np.random.Generator,
    faults: bool = True,
) -> pd.DataFrame:
    n = days * 1440
    idx = pd.date_range(start, periods=n, freq="min", tz="Asia/Kolkata")
    hour = (idx.hour + idx.minute / 60.0).to_numpy()
    tau = cfg["tau_h"] * 60

    ph = cfg["ph"] + ou(rng, n, cfg["drift"]["ph"], tau)
    tds = cfg["tds"] * (1 + ou(rng, n, cfg["drift"]["tds"], tau))
    turb = cfg["turb"] * np.exp(ou(rng, n, cfg["drift"]["turb"], tau))
    temp = cfg["temp"] + cfg["temp_amp"] * np.sin(2 * np.pi * (hour - 9) / 24) + ou(rng, n, 0.3, 360)

    prio = np.zeros(n, dtype=int)

    def mark(effect: np.ndarray, name: str) -> None:
        present = effect >= LABEL_THRESHOLD
        p = EVENT_PRIO[name]
        prio[present & (prio < p)] = p

    # Rain: turbidity up, TDS diluted by run-off, pH slightly down.
    for _ in range(rng.poisson(cfg["rain_per_day"] * days)):
        t0, u = int(rng.integers(0, n)), rng.uniform(0.5, 1.5)
        s = shape(n, t0, 60, rng.uniform(30, 180), 240) * u
        turb += cfg["rain"]["turb"] * s
        tds *= 1 + cfg["rain"]["tds"] * s
        ph += cfg["rain"]["ph"] * s
        mark(s, "rain")

    # Morning ritual bathing (06:00 ± 30 min, lasting 2-4 h) at the ghats / kund.
    if cfg.get("bathing"):
        for d in range(days):
            t0 = d * 1440 + 6 * 60 + int(rng.integers(-30, 30))
            u = rng.uniform(0.6, 1.4)
            s = shape(n, t0, 30, rng.uniform(120, 240), 60) * u
            turb += cfg["bathing"]["turb"] * s
            tds += cfg["bathing"]["tds"] * s
            mark(s, "bathing")

    # Sewage / effluent discharge: turbidity and TDS jump, pH falls, slight warming.
    k = max(int(rng.poisson(cfg["contam_per_day"] * days)), 2)
    for _ in range(k):
        t0 = int(rng.integers(int(0.05 * n), int(0.95 * n)))
        s = shape(n, t0, 10, rng.uniform(30, 180), 40)
        turb += rng.uniform(15, 80) * s
        tds += rng.uniform(150, 400) * s
        ph -= rng.uniform(0.3, 0.8) * s
        temp += rng.uniform(0.2, 0.8) * s
        mark(s, "contamination")

    obs = {
        "ph": ph + rng.normal(0, NOISE["ph"], n),
        "tds": tds + rng.normal(0, NOISE["tds"], n),
        "turb": turb + rng.normal(0, NOISE["turb"], n) * (1 + turb / 50),
        "temp": temp + rng.normal(0, NOISE["temp"], n),
    }
    fault = np.array(["none"] * n, dtype=object)

    if faults:
        if rng.random() < 0.5:  # stuck sensor
            p = str(rng.choice(["ph", "tds", "turb"]))
            t0, dur = int(rng.integers(0, n - 600)), int(rng.uniform(120, 480))
            obs[p][t0 : t0 + dur] = obs[p][t0]
            fault[t0 : t0 + dur] = "flatline"
        for i in rng.choice(n, int(0.002 * n), replace=False):  # electrical spikes
            p = str(rng.choice(["ph", "tds", "turb"]))
            if p == "ph":
                obs[p][i] += rng.choice([-1, 1]) * rng.uniform(1, 3)
            else:
                obs[p][i] *= rng.uniform(2, 5)
            fault[i] = "spike"
        for _ in range(int(rng.integers(1, 4))):  # power / link dropouts
            t0, dur = int(rng.integers(0, n - 100)), int(rng.uniform(10, 90))
            for p in obs:
                obs[p][t0 : t0 + dur] = np.nan
            fault[t0 : t0 + dur] = "dropout"

    for p, (lo, hi) in RANGES.items():
        obs[p] = np.clip(obs[p], lo, hi)

    inv = {v: k for k, v in EVENT_PRIO.items()}
    return pd.DataFrame(
        {
            "ts": idx,
            "source": key,
            "ph": obs["ph"],
            "tds": obs["tds"],
            "turb": obs["turb"],
            "temp": obs["temp"],
            "prio": prio,
            "event": [inv[p] for p in prio],
            "fault": fault,
        }
    )


def generate(days: int = 21, seed: int = 42, start: str = "2026-06-01", faults: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    parts = [gen_site(k, cfg, start, days, rng, faults) for k, cfg in SITES.items()]
    df = pd.concat(parts, ignore_index=True)
    df["wqi"] = wqi(df["ph"], df["tds"], df["turb"])
    return df
