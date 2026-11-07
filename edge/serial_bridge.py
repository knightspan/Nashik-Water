#!/usr/bin/env python3
"""serial_bridge.py — send Arduino readings from a USB port straight to the website.

For testing with the sensors on a laptop, before the ESP8266 / Raspberry Pi set-up.
Reads the Arduino over USB serial and posts the reading to the website as the real node
(default: Ramkund) every --interval seconds.

    python serial_bridge.py --port COM5                 # Windows
    python serial_bridge.py --port /dev/ttyACM0         # Linux / Raspberry Pi
    npm run bridge -- COM5                              # from the project root

Understands two line formats:
  * the pH sample sketch:   "Voltage:2.06    pH value: 7.22"
  * our node firmware JSON: {"node":"node_01","ph":7.82,"tds":331.4,"turb":15.2,"temp":24.56,...}

Verdict: the Random Forest needs all four sensors and 2.5 h of history (that runs on the Pi,
edge_ai.py). With fewer sensors this bridge uses a transparent rule instead and never
reports RED — pH alone cannot tell sewage from a natural change:
  pH 6.5-8.5 (BIS IS 10500)  -> GREEN  Normal
  outside 6.5-8.5            -> AMBER  Natural change ("worth a look")
  outside 2-12 / no reading  -> GREY   Sensor check

Close the Arduino IDE Serial Monitor first: only one program can open the port.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PH_TEXT = re.compile(r"pH\s*value\s*:\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
PARAMS = ("ph", "tds", "turb", "temp")
RANGES = {"ph": (0.0, 14.0), "tds": (0.0, 2000.0), "turb": (0.0, 3000.0), "temp": (0.0, 50.0)}

_SI = {"ph": 8.5, "tds": 500.0, "turb": 5.0}
_INV = {k: 1.0 / v for k, v in _SI.items()}
W = {k: v / sum(_INV.values()) for k, v in _INV.items()}


def wqi(ph: float, tds: float, turb: float) -> float:
    q_ph = 100 * (ph - 7) / 1.5 if ph >= 7 else 100 * (7 - ph) / 0.5
    return W["ph"] * q_ph + W["tds"] * 100 * tds / 500 + W["turb"] * 100 * turb / 5


def parse_line(line: str) -> dict[str, float]:
    """Readings found in one serial line (empty dict if none)."""
    line = line.strip()
    out: dict[str, float] = {}
    if line.startswith("{"):
        try:
            data = json.loads(line)
        except ValueError:
            return out
        for p in PARAMS:
            v = data.get(p)
            if isinstance(v, int | float):
                out[p] = float(v)
        if data.get("temp_ok") in (0, False):
            out.pop("temp", None)
        return out
    m = PH_TEXT.search(line)
    if m:
        out["ph"] = float(m.group(1))
    return out


def verdict(values: dict[str, float | None]) -> tuple[str, str, str]:
    """(colour, label, health) from the window medians — a rule, never RED."""
    ph = values.get("ph")
    if ph is None:
        return "GREY", "Sensor check", "offline"
    if not 2.0 <= ph <= 12.0:
        return "GREY", "Sensor check", "out_of_range"
    if 6.5 <= ph <= 8.5:
        return "GREEN", "Normal", "ok"
    return "AMBER", "Natural change", "ok"


@dataclass
class Window:
    """Readings collected between two posts."""

    values: dict[str, list[float]] = field(default_factory=lambda: {p: [] for p in PARAMS})
    lines: int = 0

    def add(self, reading: dict[str, float]) -> None:
        self.lines += 1
        for p, v in reading.items():
            self.values[p].append(v)

    def record(self, site: str, now: datetime) -> dict[str, Any] | None:
        if not self.lines:
            return None
        med: dict[str, float | None] = {}
        for p in PARAMS:
            vals = self.values[p]
            v = statistics.median(vals) if vals else None
            lo, hi = RANGES[p]
            med[p] = round(v, 2) if v is not None and lo <= v <= hi else None
        colour, label, health = verdict(med)
        full = all(med[p] is not None for p in ("ph", "tds", "turb"))
        return {
            "source": site,
            "colour": colour,
            "label": label,
            "confidence": None,
            "wqi": round(wqi(med["ph"], med["tds"], med["turb"]), 1) if full else None,  # type: ignore[arg-type]
            **med,
            "health": health,
            "synthetic": False,
            "latency_ms": 0.0,
            "updated": now.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
            "ts": now.astimezone(UTC).replace(microsecond=0).isoformat(),
        }


def default_key() -> str:
    """WEB_API_KEY from the environment, else INGEST_API_KEY from backend/.env (local dev)."""
    import os

    if os.environ.get("WEB_API_KEY"):
        return os.environ["WEB_API_KEY"]
    env = ROOT / "backend" / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("INGEST_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


class Poster:
    """POSTs records; keeps unsent ones (with their timestamps) and retries in a batch."""

    def __init__(self, api: str, key: str) -> None:
        import httpx

        self.url = api.rstrip("/") + "/api/ingest/batch"
        self.http = httpx.Client(timeout=15, headers={"X-API-Key": key})
        self.pending: list[dict[str, Any]] = []

    def send(self, rec: dict[str, Any]) -> str:
        import httpx

        self.pending = [*self.pending, rec][-5000:]
        try:
            res = self.http.post(self.url, json=self.pending)
        except httpx.HTTPError as exc:
            return f"website unreachable ({exc.__class__.__name__}) - {len(self.pending)} queued"
        if res.status_code == 401:
            raise SystemExit("API key rejected (401). Use the current key from Admin → API key (--key).")
        if res.status_code >= 400:
            if res.status_code < 500:
                self.pending = []  # invalid record: retrying will not help
            return f"website returned {res.status_code}: {res.text[:200]}"
        self.pending = []
        return "sent"


def run(args: argparse.Namespace) -> int:
    import serial

    poster = Poster(args.api, args.key)
    print(f"Bridge: {args.port} @ {args.baud} baud  ->  {args.api}  as site '{args.site}', every {args.interval:g} s")
    while True:
        try:
            with serial.serial_for_url(args.port, baudrate=args.baud, timeout=1) as ser:
                time.sleep(2)  # the UNO resets when the port opens
                ser.reset_input_buffer()
                print("Connected. Waiting for readings ... (Ctrl+C to stop)")
                window, deadline = Window(), time.monotonic() + args.interval
                while True:
                    raw = ser.readline().decode(errors="ignore")
                    if raw.strip():
                        reading = parse_line(raw)
                        if reading:
                            window.add(reading)
                        elif args.verbose:
                            print(f"  (ignored) {raw.strip()}")
                    if time.monotonic() >= deadline:
                        rec = window.record(args.site, datetime.now(UTC))
                        if rec is None:
                            print("No readings in the last interval - is the sketch printing 'pH value: ...'?")
                        else:
                            status = poster.send(rec)
                            shown = "  ".join(f"{p} {rec[p]}" for p in PARAMS if rec[p] is not None)
                            print(
                                f"{datetime.now():%H:%M:%S}  {shown}  ->  {rec['colour']} {rec['label']}"
                                f"  ({window.lines} lines)  {status}"
                            )
                        window, deadline = Window(), time.monotonic() + args.interval
        except serial.SerialException as exc:
            msg = str(exc)
            if "Access is denied" in msg or "PermissionError" in msg or "busy" in msg.lower():
                print(f"{args.port} is busy - close the Arduino IDE Serial Monitor / Serial Plotter.")
            else:
                print(f"Serial error: {msg}")
            if args.once_connect:
                return 1
            print("Retrying in 5 s ...")
            time.sleep(5)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", required=True, help="COM5 on Windows, /dev/ttyACM0 on Linux")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--site", default="ramkund", help="website site id this probe belongs to")
    ap.add_argument("--api", default="http://localhost:8000", help="website back-end URL")
    ap.add_argument("--key", default=None, help="ingest API key (default: backend/.env)")
    ap.add_argument("--interval", type=float, default=10, help="seconds between posts")
    ap.add_argument("--verbose", action="store_true", help="show lines that were not readings")
    ap.add_argument("--once-connect", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    args.key = args.key or default_key()
    if not args.key:
        ap.error("no API key: pass --key or set WEB_API_KEY")
    try:
        return run(args)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
