#!/usr/bin/env python3
"""replay.py — virtual nodes for the website demo (no Raspberry Pi needed).

Posts one realistic status record per simulated site every --interval seconds to the
real POST /api/ingest/batch endpoint (with the API key), marked "synthetic": true so the
website shows a SIMULATED badge. On start it back-fills --backfill-hours of history so
the charts are not empty.

    python replay.py                                   # run forever (env: SIM_API_URL, SIM_API_KEY)
    python replay.py --backfill-hours 48 --once        # back-fill, post once, exit
    python replay.py --event contamination --site tapovan   # demo event for the viva
    python replay.py --event rain --site nandini --minutes 90

Behaviour per site: slow random drift, a daily temperature cycle, morning ritual bathing
06:00-10:00 at Ramkund and Kushavart (AMBER), occasional rain run-off (AMBER) and rare
contamination (RED: turbidity +15-80 NTU, TDS +150-400 mg/L, pH -0.3 to -0.8).
Ramkund is the real node and is skipped unless --include-ramkund is given.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

IST = ZoneInfo("Asia/Kolkata")
log = logging.getLogger("simulator")

# --------------------------------------------------------------------------- WQI (same formula as the API)
_SI = {"ph": 8.5, "tds": 500.0, "turb": 5.0}
_INV = {k: 1.0 / v for k, v in _SI.items()}
W = {k: v / sum(_INV.values()) for k, v in _INV.items()}  # 0.368 / 0.006 / 0.626


def wqi(ph: float, tds: float, turb: float) -> float:
    q_ph = 100 * (ph - 7) / 1.5 if ph >= 7 else 100 * (7 - ph) / 0.5
    return W["ph"] * q_ph + W["tds"] * 100 * tds / 500 + W["turb"] * 100 * turb / 5


# --------------------------------------------------------------------------- site behaviour
BASELINES: dict[str, dict[str, float]] = {
    "ugamsthan": dict(ph=7.3, tds=110, turb=3, temp=22.0),
    "kushavart": dict(ph=7.6, tds=280, turb=10, temp=24.0),
    "gangapur_dam": dict(ph=7.6, tds=165, turb=5, temp=23.5),
    "someshwar": dict(ph=7.7, tds=210, turb=9, temp=24.0),
    "ramkund": dict(ph=7.8, tds=330, turb=15, temp=24.5),
    "tapovan": dict(ph=7.7, tds=420, turb=22, temp=25.0),
    "nandini": dict(ph=7.3, tds=650, turb=35, temp=26.0),
}
DEFAULT_BASELINE = dict(ph=7.5, tds=250, turb=10, temp=24.0)
BATHING_SITES = {"ramkund", "kushavart"}
RAIN_PER_DAY = 0.25
CONTAM_PER_DAY = {"nandini": 0.15, "tapovan": 0.1, "ramkund": 0.08, "kushavart": 0.05}
CONTAM_DEFAULT = 0.03


@dataclass
class Event:
    kind: str  # rain | contamination
    start: datetime
    minutes: float
    turb: float
    tds: float  # absolute mg/L (contamination) or fraction (rain dilution)
    ph: float

    def envelope(self, t: datetime) -> float:
        """0-1 effect: 10 % of the duration rising, flat, then a 25 % exponential tail."""
        m = (t - self.start).total_seconds() / 60
        if m < 0:
            return 0.0
        rise, hold = max(self.minutes * 0.1, 5), self.minutes * 0.65
        if m < rise:
            return m / rise
        if m < rise + hold:
            return 1.0
        return math.exp(-(m - rise - hold) / max(self.minutes * 0.25, 10))

    def over(self, t: datetime) -> bool:
        return (t - self.start).total_seconds() / 60 > self.minutes * 2


@dataclass
class SiteSim:
    site_id: str
    rng: random.Random
    base: dict[str, float] = field(default_factory=dict)
    drift: dict[str, float] = field(default_factory=lambda: {"ph": 0.0, "tds": 0.0, "turb": 0.0, "temp": 0.0})
    events: list[Event] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.base = dict(BASELINES.get(self.site_id, DEFAULT_BASELINE))

    # -- random processes ----------------------------------------------------------
    def _ou(self, key: str, dt_min: float, sigma: float, tau_min: float) -> float:
        a = math.exp(-dt_min / tau_min)
        self.drift[key] = self.drift[key] * a + self.rng.gauss(0, sigma * math.sqrt(1 - a * a))
        return self.drift[key]

    def _maybe_start_events(self, t: datetime, dt_min: float) -> None:
        p_rain = RAIN_PER_DAY * dt_min / 1440
        if self.rng.random() < p_rain and not self._active("rain", t):
            self.add_event("rain", t)
        p_contam = CONTAM_PER_DAY.get(self.site_id, CONTAM_DEFAULT) * dt_min / 1440
        if self.rng.random() < p_contam and not self._active("contamination", t):
            self.add_event("contamination", t)

    def _active(self, kind: str, t: datetime) -> bool:
        return any(e.kind == kind and not e.over(t) for e in self.events)

    def add_event(self, kind: str, t: datetime, minutes: float | None = None, immediate: bool = False) -> Event:
        """Start an event at t. immediate=True (demo events) skips the ramp-up, so the
        site changes colour on the very next record."""
        ev = self._make_event(kind, t, minutes)
        if immediate:
            ev.start = t - timedelta(minutes=max(ev.minutes * 0.1, 5))
        self.events.append(ev)
        log.info("event", extra={"site": self.site_id, "kind": kind, "minutes": round(ev.minutes)})
        return ev

    def _make_event(self, kind: str, t: datetime, minutes: float | None) -> Event:
        r = self.rng
        if kind == "contamination":
            ev = Event(
                kind, t, minutes or r.uniform(30, 120), r.uniform(15, 80), r.uniform(150, 400), -r.uniform(0.3, 0.8)
            )
        elif kind == "rain":
            ev = Event(
                kind, t, minutes or r.uniform(60, 240), r.uniform(20, 120), -r.uniform(0.1, 0.3), -r.uniform(0.05, 0.15)
            )
        else:
            raise ValueError(f"unknown event kind {kind!r}")
        return ev

    @staticmethod
    def bathing(t: datetime) -> float:
        """Morning ritual bathing 06:00-10:00 IST: rises by 06:30, holds to 09:00, fades by 10:00."""
        h = t.astimezone(IST)
        x = h.hour + h.minute / 60
        if 6.0 <= x < 6.5:
            return (x - 6.0) / 0.5
        if 6.5 <= x < 9.0:
            return 1.0
        if 9.0 <= x < 10.0:
            return 1.0 - (x - 9.0)
        return 0.0

    # -- one reading ---------------------------------------------------------------
    def step(self, t: datetime, dt_min: float, spontaneous: bool = True) -> dict[str, Any]:
        b, r = self.base, self.rng
        if spontaneous:
            self._maybe_start_events(t, dt_min)
        self.events = [e for e in self.events if not e.over(t)]

        ph = b["ph"] + self._ou("ph", dt_min, 0.06, 480)
        tds = b["tds"] * (1 + self._ou("tds", dt_min, 0.05, 480))
        turb = b["turb"] * math.exp(self._ou("turb", dt_min, 0.2, 480))
        hour = t.astimezone(IST).hour + t.astimezone(IST).minute / 60
        temp = b["temp"] + 1.4 * math.sin(2 * math.pi * (hour - 9) / 24) + self._ou("temp", dt_min, 0.3, 360)

        state = "normal"
        bath = self.bathing(t) * (1.0 if self.site_id in BATHING_SITES else 0.0)
        if bath > 0:
            turb += 20 * bath
            tds += 50 * bath
            if bath >= 0.15:
                state = "bathing"
        for e in self.events:
            s = e.envelope(t)
            if e.kind == "rain":
                turb += e.turb * s
                tds *= 1 + e.tds * s
                ph += e.ph * s
                if s >= 0.15 and state == "normal":
                    state = "rain"
            else:
                turb += e.turb * s
                tds += e.tds * s
                ph += e.ph * s
                temp += 0.5 * s
                if s >= 0.15:
                    state = "contamination"

        ph = min(max(ph + r.gauss(0, 0.02), 0.0), 14.0)
        tds = min(max(tds + r.gauss(0, 3.0), 0.0), 2000.0)
        turb = min(max(turb + r.gauss(0, 0.5) * (1 + turb / 50), 0.0), 3000.0)
        temp = min(max(temp + r.gauss(0, 0.06), 0.0), 50.0)

        if state == "contamination":
            colour, label, conf = "RED", "Contamination", r.uniform(78, 97)
        elif state in ("bathing", "rain"):
            colour, label, conf = "AMBER", "Natural change", r.uniform(80, 97)
        else:
            colour, label, conf = "GREEN", "Normal", r.uniform(90, 99.5)

        return {
            "source": self.site_id,
            "colour": colour,
            "label": label,
            "confidence": round(conf, 1),
            "wqi": round(wqi(ph, tds, turb), 1),
            "ph": round(ph, 2),
            "tds": round(tds, 1),
            "turb": round(turb, 2),
            "temp": round(temp, 2),
            "health": "ok",
            "synthetic": True,
            "latency_ms": round(r.uniform(6, 20), 2),
            "updated": t.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
            "ts": t.astimezone(UTC).isoformat(),
        }


# --------------------------------------------------------------------------- control file (viva events)
def control_path() -> Path:
    return Path(os.environ.get("SIM_CONTROL_DIR", tempfile.gettempdir())) / "nashik_sim_control.json"


def heartbeat_path() -> Path:
    return control_path().with_name("nashik_sim_heartbeat")


def read_requests() -> list[dict[str, Any]]:
    p = control_path()
    if not p.exists():
        return []
    try:
        reqs = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        reqs = []
    p.unlink(missing_ok=True)
    return reqs if isinstance(reqs, list) else []


def queue_request(req: dict[str, Any]) -> None:
    p = control_path()
    existing: list[dict[str, Any]] = []
    if p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            existing = []
    p.write_text(json.dumps([*existing, req]), encoding="utf-8")


def runner_alive(max_age_s: float) -> bool:
    try:
        return time.time() - heartbeat_path().stat().st_mtime < max_age_s
    except OSError:
        return False


# --------------------------------------------------------------------------- HTTP
class Client:
    def __init__(self, api: str, key: str, timeout: float = 15.0) -> None:
        self.api = api.rstrip("/")
        self.http = httpx.Client(timeout=timeout, headers={"X-API-Key": key})
        self.pending: list[dict[str, Any]] = []  # survives API outages, like the Pi's queue

    def wait_ready(self, max_wait_s: float = 300) -> None:
        deadline = time.time() + max_wait_s
        while True:
            try:
                if self.http.get(f"{self.api}/api/health").status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            if time.time() > deadline:
                raise SystemExit(f"API at {self.api} not reachable")
            log.info("waiting for API ...")
            time.sleep(3)

    def latest_ts(self) -> dict[str, datetime]:
        res = self.http.get(f"{self.api}/api/sources")
        res.raise_for_status()
        return {s["id"]: datetime.fromisoformat(s["latest"]["ts"]) for s in res.json() if s["latest"]}

    def simulated_sites(self, include_ramkund: bool) -> list[str]:
        res = self.http.get(f"{self.api}/api/sources")
        res.raise_for_status()
        ids = [s["id"] for s in res.json() if s["simulated"]]
        if include_ramkund and "ramkund" not in ids:
            ids.append("ramkund")
        return ids

    def send(self, records: list[dict[str, Any]]) -> bool:
        self.pending.extend(records)
        self.pending = self.pending[-20_000:]
        while self.pending:
            chunk = self.pending[:500]
            try:
                res = self.http.post(f"{self.api}/api/ingest/batch", json=chunk)
            except httpx.HTTPError as exc:
                log.warning("API unreachable, %d records queued (%s)", len(self.pending), exc)
                return False
            if res.status_code == 401:
                raise SystemExit("API key rejected (401). Set SIM_API_KEY to the current ingest key.")
            if res.status_code >= 500 or res.status_code == 429:
                log.warning("API returned %s, will retry", res.status_code)
                return False
            if res.status_code >= 400:
                log.error("API rejected batch: %s %s", res.status_code, res.text[:300])
            else:
                body = res.json()
                log.info("posted", extra=body)
            self.pending = self.pending[len(chunk) :]
        return True


# --------------------------------------------------------------------------- main loops
def backfill(
    sims: dict[str, SiteSim],
    hours: float,
    step_min: float,
    now: datetime,
    latest: dict[str, datetime] | None = None,
) -> list[dict[str, Any]]:
    """History for each site from `now - hours`, or from its latest stored reading if newer
    (so restarting the simulator never doubles the history)."""
    out = []
    latest = latest or {}
    for site, sim in sims.items():
        t = now - timedelta(hours=hours)
        if site in latest:
            t = max(t, latest[site] + timedelta(minutes=step_min))
        while t < now - timedelta(minutes=step_min / 2):
            out.append(sim.step(t, step_min))
            t += timedelta(minutes=step_min)
    return out


def run(args: argparse.Namespace) -> int:
    client = Client(args.api, args.key)
    client.wait_ready()
    site_ids = args.sites or client.simulated_sites(args.include_ramkund)
    rng = random.Random(args.seed)
    sims = {s: SiteSim(s, random.Random(rng.random())) for s in site_ids}
    log.info("simulating %s", ", ".join(site_ids))

    now = datetime.now(UTC).replace(microsecond=0)
    if args.backfill_hours > 0:
        hist = backfill(sims, args.backfill_hours, args.backfill_step, now, client.latest_ts())
        log.info("back-filling %d records (%.0f h)", len(hist), args.backfill_hours)
        client.send(hist)

    sim_clock = now
    while True:
        heartbeat_path().touch()
        for req in read_requests():
            sim = sims.get(req.get("site", ""))
            if sim is None:
                log.warning("event for unknown/non-simulated site %s ignored", req.get("site"))
                continue
            sim.add_event(req["kind"], sim_clock, req.get("minutes"), immediate=True)
        now = datetime.now(UTC).replace(microsecond=0)
        dt_min = args.interval / 60 * args.speed
        sim_clock += timedelta(minutes=dt_min)
        # Values evolve on the (possibly accelerated) sim clock; the record carries wall time.
        records = [{**s.step(sim_clock, dt_min), "ts": now.isoformat()} for s in sims.values()]
        client.send(records)
        if args.once:
            return 0
        # Sleep until the next tick, but wake within a second for a demo event request.
        deadline = time.monotonic() + args.interval
        while time.monotonic() < deadline and not control_path().exists():
            time.sleep(1)


def trigger_event(args: argparse.Namespace) -> int:
    req = {"site": args.site, "kind": args.event, "minutes": args.minutes}
    if runner_alive(max_age_s=max(3 * args.interval, 180)):
        queue_request(req)
        print(f"Queued {args.event} at {args.site} — the running simulator applies it within a second.")
        return 0
    # No simulator running: play the event ourselves, one record per interval.
    print(f"No running simulator found; posting the {args.event} event at {args.site} directly.")
    client = Client(args.api, args.key)
    client.wait_ready(30)
    sim = SiteSim(args.site, random.Random(args.seed))
    start = datetime.now(UTC).replace(microsecond=0)
    ev = sim.add_event(args.event, start, args.minutes, immediate=True)
    end = start + timedelta(minutes=ev.minutes * 1.2)
    while datetime.now(UTC) < end:
        t = datetime.now(UTC).replace(microsecond=0)
        rec = sim.step(t, args.interval / 60, spontaneous=False)
        client.send([rec])
        print(f"{t:%H:%M:%S} {args.site}: {rec['colour']} {rec['label']} WQI {rec['wqi']}")
        if args.once:
            break
        time.sleep(args.interval)
    return 0


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default=os.environ.get("SIM_API_URL", "http://localhost:8000"))
    ap.add_argument("--key", default=os.environ.get("SIM_API_KEY") or os.environ.get("INGEST_API_KEY", ""))
    ap.add_argument(
        "--interval", type=float, default=float(os.environ.get("SIM_INTERVAL", 60)), help="seconds between posts"
    )
    ap.add_argument(
        "--speed",
        type=float,
        default=float(os.environ.get("SIM_SPEED", 1)),
        help="sim-time multiplier (events evolve faster)",
    )
    ap.add_argument("--backfill-hours", type=float, default=float(os.environ.get("SIM_BACKFILL_HOURS", 24)))
    ap.add_argument("--backfill-step", type=float, default=5.0, help="minutes between back-filled records")
    ap.add_argument("--sites", nargs="*", help="override the site list")
    ap.add_argument("--include-ramkund", action="store_true", help="also simulate the real node (demo only)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--once", action="store_true", help="post one round and exit")
    ap.add_argument("--event", choices=["contamination", "rain"], help="trigger a demo event")
    ap.add_argument("--site", help="site for --event")
    ap.add_argument("--minutes", type=float, default=None, help="event duration")
    args = ap.parse_args(argv)
    if args.event and not args.site:
        ap.error("--event needs --site")
    if not args.key:
        ap.error("no API key: pass --key or set SIM_API_KEY")
    return args


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args = parse(argv)
    return trigger_event(args) if args.event else run(args)


if __name__ == "__main__":
    raise SystemExit(main())
