#!/usr/bin/env python3
"""synth_water.py - mock telemetry for 7 Nashik water sources ("virtual nodes").

Two jobs:
  generate  -> write a labelled 1-minute dataset for training the AI models
  replay    -> publish that dataset live over MQTT, exactly like a real node,
               so the website, AI and alerts treat virtual and real sources the same

The output has the same columns as logger.py (ts, source, ph, tds, turb, temp ...)
so a model trained on it runs unchanged on the real probe. Every row carries
is_synthetic=1 plus ground-truth labels: `event` (what happened to the water)
and `fault` (what went wrong with the sensor).

Baselines below are PLACEHOLDERS. Replace them with your own 7 field tests and
replace NOISE with the standard deviations from experiment E2 (30 readings in
the same water), so the mock data matches your actual probes.

Usage:
  python synth_water.py generate --days 14 --out data/synthetic_1min.csv
  python synth_water.py replay --csv data/synthetic_1min.csv --speed 1
"""
import argparse
import json
import time

import numpy as np
import pandas as pd
from scipy.signal import lfilter

# ---------- WQI (same formula as prepare.py) ----------
SI = {"ph": 8.5, "tds": 500.0, "turb": 5.0}
_inv = {k: 1.0 / v for k, v in SI.items()}
W = {k: v / sum(_inv.values()) for k, v in _inv.items()}


def wqi(ph, tds, turb):
    ph = np.asarray(ph, float)
    q_ph = np.where(ph >= 7.0, 100 * (ph - 7.0) / 1.5, 100 * (7.0 - ph) / 0.5)
    return W["ph"] * q_ph + W["tds"] * 100 * np.asarray(tds) / 500 + W["turb"] * 100 * np.asarray(turb) / 5


# ---------- measurement noise of YOUR probes (replace with E2 results) ----------
NOISE = {"ph": 0.02, "tds": 3.0, "turb": 0.5, "temp": 0.06}
RANGES = {"ph": (0, 14), "tds": (0, 2000), "turb": (0, 3000), "temp": (0, 50)}

# ---------- sources (PLACEHOLDER baselines - replace with your field tests) ----------
# drift: size of slow natural wandering (pH units, fraction of TDS, log-turbidity)
# rain:  added turbidity (NTU), fractional TDS change, pH change at full intensity
SOURCES = {
    "ugamsthan_trimbakeshwar": dict(
        name="Ugamsthan, Trimbakeshwar (origin of Godavari)", kind="spring", lat=19.9236, lon=73.5186,
        ph=7.3, tds=110, turb=3, temp=22.0, temp_amp=1.0, tau_h=12,
        drift=dict(ph=0.04, tds=0.04, turb=0.20),
        rain_per_day=0.20, rain=dict(turb=40, tds=-0.10, ph=-0.08),
        contam_per_day=0.02),
    "kushavart": dict(
        name="Kushavart Kund, Trimbakeshwar", kind="kund", lat=19.9327, lon=73.5306,
        ph=7.6, tds=280, turb=10, temp=24.0, temp_amp=1.5, tau_h=10,
        drift=dict(ph=0.05, tds=0.05, turb=0.25),
        rain_per_day=0.20, rain=dict(turb=30, tds=-0.10, ph=-0.08),
        bathing=dict(turb=15, tds=40), contam_per_day=0.08),
    "someshwar": dict(
        name="Godavari at Someshwar", kind="river", lat=20.0236, lon=73.7383,
        ph=7.7, tds=210, turb=9, temp=24.0, temp_amp=1.4, tau_h=8,
        drift=dict(ph=0.06, tds=0.05, turb=0.25),
        rain_per_day=0.20, rain=dict(turb=90, tds=-0.25, ph=-0.12),
        contam_per_day=0.05),
    "gangapur_dam": dict(
        name="Gangapur Dam", kind="reservoir", lat=20.0400, lon=73.6700,
        ph=7.6, tds=165, turb=5, temp=23.5, temp_amp=1.0, tau_h=12,
        drift=dict(ph=0.05, tds=0.04, turb=0.20),
        rain_per_day=0.20, rain=dict(turb=50, tds=-0.15, ph=-0.10),
        contam_per_day=0.03),
    "ramkund": dict(
        name="Ramkund (Godavari ghats)", kind="river", lat=20.0074, lon=73.7924,
        ph=7.8, tds=330, turb=15, temp=24.5, temp_amp=1.5, tau_h=8,
        drift=dict(ph=0.08, tds=0.06, turb=0.25),
        rain_per_day=0.20, rain=dict(turb=120, tds=-0.30, ph=-0.15),
        bathing=dict(turb=20, tds=50), contam_per_day=0.12),
    "tapovan": dict(
        name="Tapovan (Godavari)", kind="river", lat=20.0035, lon=73.8135,
        ph=7.7, tds=420, turb=22, temp=25.0, temp_amp=1.5, tau_h=8,
        drift=dict(ph=0.08, tds=0.06, turb=0.25),
        rain_per_day=0.20, rain=dict(turb=120, tds=-0.30, ph=-0.15),
        contam_per_day=0.15),
    "nandini": dict(
        name="Nandini (Nasardi) river", kind="urban river", lat=19.9900, lon=73.7700,
        ph=7.3, tds=650, turb=35, temp=26.0, temp_amp=1.2, tau_h=6,
        drift=dict(ph=0.08, tds=0.07, turb=0.30),
        rain_per_day=0.20, rain=dict(turb=150, tds=-0.30, ph=-0.15),
        contam_per_day=0.20),
}

# higher number wins when events overlap
EVENT_PRIO = {"normal": 0, "rain": 1, "bathing": 2, "contamination": 4}


# ---------- building blocks ----------
def ou(rng, n, sigma, tau_min):
    """Ornstein-Uhlenbeck noise: slow, mean-reverting natural wandering."""
    a = np.exp(-1.0 / tau_min)
    e = rng.normal(0, sigma * np.sqrt(1 - a * a), n)
    return lfilter([1.0], [1.0, -a], e)


def shape(n, t0, rise, hold, tau, amp):
    """Linear rise, flat hold, exponential decay. Returns an array of length n."""
    y = np.zeros(n)
    t = np.arange(n) - t0
    rise = max(rise, 1)
    up = (t >= 0) & (t < rise)
    y[up] = amp * t[up] / rise
    flat = (t >= rise) & (t < rise + hold)
    y[flat] = amp
    down = t >= rise + hold
    y[down] = amp * np.exp(-(t[down] - rise - hold) / tau)
    return y


def gen_source(key, cfg, start, days, rng, log):
    n = days * 1440
    idx = pd.date_range(start, periods=n, freq="min", tz="Asia/Kolkata")
    hour = (idx.hour + idx.minute / 60.0).to_numpy()
    tau = cfg["tau_h"] * 60

    # natural baseline
    ph = cfg["ph"] + ou(rng, n, cfg["drift"]["ph"], tau)
    tds = cfg["tds"] * (1 + ou(rng, n, cfg["drift"]["tds"], tau))
    turb = cfg["turb"] * np.exp(ou(rng, n, cfg["drift"]["turb"], tau))
    temp = (cfg["temp"] + cfg["temp_amp"] * np.sin(2 * np.pi * (hour - 9) / 24)
            + ou(rng, n, 0.3, 360))

    event = np.array(["normal"] * n, dtype=object)
    prio = np.zeros(n)
    flow = np.ones(n, dtype=int)

    def mark(t0, t1, name):
        sl = slice(max(int(t0), 0), min(int(t1), n))
        p = EVENT_PRIO[name]
        m = prio[sl] < p
        event[sl][m] = name
        prio[sl][m] = p

    def note(kind, t0, t1, **kw):
        log.append(dict(source=key, type=kind,
                        start=str(idx[max(int(t0), 0)]), end=str(idx[min(int(t1), n - 1)]),
                        **{k: round(float(v), 2) for k, v in kw.items()}))

    # rain: turbidity up, TDS diluted by run-off
    for _ in range(rng.poisson(cfg["rain_per_day"] * days)):
        t0, u = rng.integers(0, n), rng.uniform(0.5, 1.5)
        hold = rng.uniform(30, 180)
        s = shape(n, t0, 60, hold, 240, 1.0) * u
        turb += cfg["rain"]["turb"] * s
        tds *= 1 + cfg["rain"]["tds"] * s
        ph += cfg["rain"]["ph"] * s
        mark(t0, t0 + 60 + hold + 720, "rain")
        note("rain", t0, t0 + 60 + hold + 720, intensity=u)

    # morning ritual bathing at the ghats / kund: turbidity and TDS rise, then settle
    if cfg.get("bathing"):
        for d in range(days):
            t0 = d * 1440 + int(6 * 60) + rng.integers(-30, 30)
            hold = rng.uniform(120, 240); u = rng.uniform(0.6, 1.4)
            s_ = shape(n, t0, 30, hold, 60, 1.0) * u
            turb += cfg["bathing"]["turb"] * s_
            tds += cfg["bathing"]["tds"] * s_
            mark(t0, t0 + 30 + hold + 120, "bathing")

    # sewage / effluent discharge (contamination): turbidity and TDS jump, pH falls
    k = rng.poisson(cfg["contam_per_day"] * days)
    k = max(k, 2)                                    # every source gets at least two labelled events
    for _ in range(k):
        t0 = rng.integers(int(0.05 * n), int(0.95 * n))
        hold = rng.uniform(30, 180)
        a_turb, a_tds, a_ph = rng.uniform(15, 80), rng.uniform(150, 400), rng.uniform(0.3, 0.8)
        s = shape(n, t0, 10, hold, 40, 1.0)
        turb += a_turb * s
        tds += a_tds * s
        ph -= a_ph * s
        temp += rng.uniform(0.2, 0.8) * s
        mark(t0, t0 + 10 + hold + 120, "contamination")
        note("contamination", t0, t0 + 10 + hold + 120, turb=a_turb, tds=a_tds, ph=-a_ph)

    true = dict(ph=ph.copy(), tds=tds.copy(), turb=turb.copy(), temp=temp.copy())

    # ---------- measurement noise ----------
    ph = ph + rng.normal(0, NOISE["ph"], n)
    tds = tds + rng.normal(0, NOISE["tds"], n)
    turb = turb + rng.normal(0, NOISE["turb"], n) * (1 + turb / 50)
    temp = temp + rng.normal(0, NOISE["temp"], n)
    obs = dict(ph=ph, tds=tds, turb=turb, temp=temp)

    # ---------- sensor faults (what the sensor-health model must catch) ----------
    fault = np.array(["none"] * n, dtype=object)

    if rng.random() < 0.6:                           # pH probe drift
        t0 = rng.integers(0, int(0.6 * n))
        total = rng.uniform(0.3, 1.0) * rng.choice([-1, 1])
        dur = rng.uniform(2, 5) * 1440
        d = np.clip((np.arange(n) - t0) / dur, 0, 1) * total
        d[int(t0 + dur):] = 0                        # recalibrated at the next buffer check
        obs["ph"] += d
        fault[np.abs(d) > 0.1] = "ph_drift"
        note("fault_ph_drift", t0, min(t0 + dur, n - 1), total=total)

    if rng.random() < 0.5:                           # turbidity window fouling
        t0 = rng.integers(0, int(0.7 * n))
        dur = rng.uniform(1, 3) * 1440
        bias = np.clip((np.arange(n) - t0) / dur, 0, 1) * rng.uniform(5, 20)
        bias[int(t0 + dur):] = 0                     # cleaned at the end
        obs["turb"] += bias
        fault[bias > 1] = "fouling"
        note("fault_fouling", t0, t0 + dur, max_bias=bias.max())

    if rng.random() < 0.5:                           # stuck sensor (flatline)
        p = rng.choice(["ph", "tds", "turb"])
        t0, dur = rng.integers(0, n - 600), int(rng.uniform(120, 480))
        obs[p][t0:t0 + dur] = obs[p][t0]
        fault[t0:t0 + dur] = "flatline"
        note("fault_flatline", t0, t0 + dur, minutes=dur)

    for i in rng.choice(n, int(0.002 * n), replace=False):   # electrical spikes
        p = rng.choice(["ph", "tds", "turb"])
        obs[p][i] = obs[p][i] + rng.choice([-1, 1]) * rng.uniform(1, 3) if p == "ph" \
            else obs[p][i] * rng.uniform(2, 5)
        fault[i] = "spike"

    for _ in range(rng.integers(1, 4)):              # dropouts (power or link loss)
        t0, dur = rng.integers(0, n - 100), int(rng.uniform(10, 90))
        for p in obs:
            obs[p][t0:t0 + dur] = np.nan
        fault[t0:t0 + dur] = "dropout"

    for p, (lo, hi) in RANGES.items():
        obs[p] = np.clip(obs[p], lo, hi)

    return pd.DataFrame({
        "epoch": ((idx - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1s")).astype(np.int64),
        "ts": idx.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source": key,
        "ph": np.round(obs["ph"], 3), "tds": np.round(obs["tds"], 1),
        "turb": np.round(obs["turb"], 2), "temp": np.round(obs["temp"], 2),
        "settling": 0, "flow": flow,
        "wqi": np.round(wqi(obs["ph"], obs["tds"], obs["turb"]), 2),
        "wqi_true": np.round(wqi(true["ph"], true["tds"], np.clip(true["turb"], 0, None)), 2),
        "event": event, "fault": fault, "is_synthetic": 1,
    })


def generate(args):
    rng = np.random.default_rng(args.seed)
    log, parts = [], []
    for key, cfg in SOURCES.items():
        parts.append(gen_source(key, cfg, args.start, args.days, rng, log))
    df = pd.concat(parts, ignore_index=True)
    df.to_csv(args.out, index=False)
    with open(args.out.rsplit(".", 1)[0] + "_events.json", "w") as f:
        json.dump(log, f, indent=1)
    with open(args.out.rsplit(".", 1)[0] + "_sources.json", "w") as f:
        json.dump({k: {x: v[x] for x in ("name", "kind", "lat", "lon")} for k, v in SOURCES.items()},
                  f, indent=1)
    print(f"wrote {len(df):,} rows -> {args.out}")
    print(df.groupby("source")[["ph", "tds", "turb", "temp", "wqi"]].median().round(2))
    print("\nevent minutes per source:")
    print(pd.crosstab(df["source"], df["event"]))
    print("\nfault minutes per source:")
    print(pd.crosstab(df["source"], df["fault"]))


def replay(args):
    """Publish the synthetic data as live virtual nodes. speed=1 is real time."""
    import paho.mqtt.client as mqtt
    df = pd.read_csv(args.csv)
    groups = {s: g.reset_index(drop=True) for s, g in df.groupby("source")}
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.connect(args.host, 1883, 60)
    c.loop_start()
    i = 0
    while True:
        now = int(time.time())
        for src, g in groups.items():
            r = g.iloc[i % len(g)]
            if pd.isna(r["ph"]):
                continue                             # a dropout: publish nothing, like a real node
            msg = {"epoch": now, "source": src, "settling": 0,
                   "ph": float(r["ph"]), "tds": float(r["tds"]),
                   "turb": float(r["turb"]), "temp": float(r["temp"]),
                   "synthetic": True}                # the website shows a SIMULATED badge
            c.publish(f"wqi/{src}/reading", json.dumps(msg), qos=1)
        i += 1
        time.sleep(60 / args.speed)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--days", type=int, default=14)
    g.add_argument("--start", default="2026-11-01")
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--out", default="synthetic_1min.csv")
    r = sub.add_parser("replay")
    r.add_argument("--csv", default="synthetic_1min.csv")
    r.add_argument("--speed", type=float, default=1.0)
    r.add_argument("--host", default="localhost")
    a = ap.parse_args()
    generate(a) if a.cmd == "generate" else replay(a)
