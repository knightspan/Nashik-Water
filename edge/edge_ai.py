#!/usr/bin/env python3
"""edge_ai.py — real-time AI service on the Raspberry Pi 5.

Input   : 1-minute JSON readings from the Arduino node, via MQTT (ESP8266 gateway,
          topic wqi/<node>/reading) or directly over USB serial (--serial /dev/ttyACM0).
Every 5 readings per site:
          5-min window (median) -> sensor-health rules -> features -> Random Forest
          -> GREEN / AMBER / RED / GREY status record.
Output  : POST to the website (/api/ingest/batch, X-API-Key) through a persistent
          SQLite outbox that survives power cuts and internet outages; buzzer / LED /
          relay on RED; Telegram alert (max one per site per 30 min); data/status.json.

    python edge_ai.py                       # MQTT on localhost
    python edge_ai.py --serial /dev/ttyACM0 # no ESP8266: read the UNO over USB

Configuration comes from .env (see .env.example).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from wqm_ml.features import HISTORY, PARAMS, aggregate_window, latest_features
from wqm_ml.health import sensor_health
from wqm_ml.model import COLOUR, WaterModel
from wqm_ml.wqi import wqi

log = logging.getLogger("edge")
HERE = Path(__file__).resolve().parent


# --------------------------------------------------------------------------- config
def load_env(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE lines); real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass
class Config:
    web_api_url: str
    web_api_key: str
    mqtt_host: str
    node_site_map: dict[str, str]
    model_dir: Path
    data_dir: Path
    gpio: bool
    tg_token: str | None
    tg_chat: str | None
    silence_minutes: int = 10
    alert_repeat_minutes: int = 30

    @classmethod
    def from_env(cls) -> Config:
        mapping = {}
        for pair in os.environ.get("NODE_SITE_MAP", "node_01:ramkund").split(","):
            if ":" in pair:
                node, site = pair.split(":", 1)
                mapping[node.strip()] = site.strip()
        return cls(
            web_api_url=os.environ.get("WEB_API_URL", "http://localhost:8000").rstrip("/"),
            web_api_key=os.environ.get("WEB_API_KEY", ""),
            mqtt_host=os.environ.get("MQTT_HOST", "localhost"),
            node_site_map=mapping,
            model_dir=Path(os.environ.get("MODEL_DIR", HERE.parent / "ml" / "models")),
            data_dir=Path(os.environ.get("DATA_DIR", HERE / "data")),
            gpio=os.environ.get("GPIO_ENABLED", "true").lower() == "true",
            tg_token=os.environ.get("TG_TOKEN") or None,
            tg_chat=os.environ.get("TG_CHAT") or None,
        )


# --------------------------------------------------------------------------- outputs
class Outputs:
    """Buzzer (GPIO17), alert LED (GPIO27) and relay (GPIO22, active-low). No-op off the Pi."""

    def __init__(self, enabled: bool) -> None:
        self.ok = False
        if not enabled:
            return
        try:
            from gpiozero import LED, Buzzer, OutputDevice

            self.buzzer, self.led = Buzzer(17), LED(27)
            self.relay = OutputDevice(22, active_high=False)
            self.ok = True
        except Exception as exc:  # not on a Pi, or no GPIO access
            log.warning("GPIO disabled: %s", exc)

    def alarm(self, on: bool) -> None:
        if not self.ok:
            return
        if on:
            self.buzzer.beep(0.3, 0.2, n=3, background=True)
            self.led.on()
            self.relay.on()
        else:
            self.led.off()
            self.relay.off()


def telegram(cfg: Config, text: str) -> None:
    if not (cfg.tg_token and cfg.tg_chat):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{cfg.tg_token}/sendMessage",
            data={"chat_id": cfg.tg_chat, "text": text},
            timeout=5,
        )
    except requests.RequestException:
        pass  # local alarms still work offline


# --------------------------------------------------------------------------- persistent outbox
class Outbox:
    """SQLite queue of status records + raw reading log (for re-training later)."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS readings(ts TEXT, site TEXT, ph REAL, tds REAL, turb REAL, temp REAL)"
        )
        self.lock = threading.Lock()

    def put(self, record: dict[str, Any]) -> None:
        with self.lock:
            self.db.execute("INSERT INTO outbox(payload) VALUES (?)", (json.dumps(record),))
            # Keep at most ~50k records (about a month for one site at 5-min intervals).
            self.db.execute("DELETE FROM outbox WHERE id < (SELECT MAX(id) - 50000 FROM outbox)")

    def log_reading(self, ts: datetime, site: str, r: dict[str, float]) -> None:
        with self.lock:
            self.db.execute(
                "INSERT INTO readings VALUES (?,?,?,?,?,?)",
                (ts.isoformat(), site, r.get("ph"), r.get("tds"), r.get("turb"), r.get("temp")),
            )

    def peek(self, n: int) -> list[tuple[int, dict[str, Any]]]:
        with self.lock:
            rows = self.db.execute("SELECT id, payload FROM outbox ORDER BY id LIMIT ?", (n,)).fetchall()
        return [(i, json.loads(p)) for i, p in rows]

    def drop(self, ids: list[int]) -> None:
        if ids:
            with self.lock:
                self.db.execute(f"DELETE FROM outbox WHERE id IN ({','.join('?' * len(ids))})", ids)  # noqa: S608

    def size(self) -> int:
        with self.lock:
            return int(self.db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])


def uploader(cfg: Config, outbox: Outbox, stop: threading.Event) -> None:
    """Flush the outbox to the website; back off while offline. Idempotent on (source, ts)."""
    backoff = 5.0
    url = f"{cfg.web_api_url}/api/ingest/batch"
    while not stop.is_set():
        batch = outbox.peek(500)
        if not batch:
            stop.wait(5)
            continue
        try:
            res = requests.post(url, json=[p for _, p in batch], headers={"X-API-Key": cfg.web_api_key}, timeout=20)
        except requests.RequestException as exc:
            log.warning("website unreachable (%s); %d queued", exc.__class__.__name__, outbox.size())
            stop.wait(backoff)
            backoff = min(backoff * 2, 300)
            continue
        if res.status_code in (200, 201):
            outbox.drop([i for i, _ in batch])
            backoff = 5.0
            log.info("uploaded %s", res.json())
        elif res.status_code in (401, 429) or res.status_code >= 500:
            log.error("website returned %s: %s", res.status_code, res.text[:200])
            stop.wait(backoff)
            backoff = min(backoff * 2, 300)
        else:  # 404 unknown site / 422 invalid: retrying will not help
            log.error("records rejected (%s): %s", res.status_code, res.text[:300])
            outbox.drop([i for i, _ in batch])


# --------------------------------------------------------------------------- engine
@dataclass
class SiteState:
    minutes: deque[dict[str, float]] = field(default_factory=lambda: deque(maxlen=60))
    windows: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=HISTORY))
    count: int = 0
    last_seen: datetime | None = None
    last_alert: float = 0.0
    synthetic: bool = False


class EdgeEngine:
    """Pure processing logic (no network): readings in, status records out."""

    def __init__(self, model: WaterModel, baselines: dict[str, dict[str, float]] | None = None) -> None:
        self.model = model
        if hasattr(model.estimator, "n_jobs"):
            model.estimator.n_jobs = 1  # one prediction at a time: threads only add latency
        self.baselines = {**model.baselines, **(baselines or {})}
        self.sites: dict[str, SiteState] = defaultdict(SiteState)

    def baseline(self, site: str, st: SiteState) -> dict[str, float]:
        if site in self.baselines:
            return self.baselines[site]
        # Unknown site: learn from its own history until a baseline is calibrated.
        w = pd.DataFrame(list(st.windows))
        return {p: float(w[p].median()) for p in ("ph", "tds", "turb")}

    def on_reading(self, site: str, reading: dict[str, Any], ts: datetime) -> dict[str, Any] | None:
        st = self.sites[site]
        row = {p: _num(reading.get(p)) for p in PARAMS}
        if reading.get("temp_ok") in (0, False):
            row["temp"] = np.nan  # DS18B20 read failed on the UNO
        st.minutes.append(row)
        st.last_seen = ts
        st.synthetic = bool(reading.get("synthetic", False))
        st.count += 1
        if st.count % 5:
            return None
        return self.evaluate(site, ts)

    def evaluate(self, site: str, ts: datetime) -> dict[str, Any]:
        st = self.sites[site]
        last5 = np.array([[m[p] for p in PARAMS] for m in list(st.minutes)[-5:]], dtype=float)
        med = aggregate_window(last5)
        st.windows.append({"ts": ts, **dict(zip(PARAMS, med, strict=True))})
        health = sensor_health(list(st.minutes))
        values = dict(zip(PARAMS, med, strict=True))
        t0 = time.perf_counter()
        if health != "ok":
            label, conf = "Sensor check", 0.0
        else:
            x = latest_features(list(st.windows), self.baseline(site, st))
            if x is None:
                label, conf = "Learning baseline", 0.0
            else:
                label, conf = self.model.predict(x)
        latency = (time.perf_counter() - t0) * 1000
        colour = COLOUR.get(label, "GREY")
        ok = all(np.isfinite(values[p]) for p in ("ph", "tds", "turb"))
        return {
            "source": site,
            "colour": colour,
            "label": label,
            "confidence": round(conf, 1),
            "wqi": round(float(wqi(values["ph"], values["tds"], values["turb"])), 1) if ok else None,
            **{p: (round(float(v), 2) if np.isfinite(v) else None) for p, v in values.items()},
            "health": health,
            "synthetic": st.synthetic,
            "latency_ms": round(latency, 2),
            "updated": ts.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
            "ts": ts.astimezone(UTC).isoformat(),
        }

    def silence_check(self, now: datetime, silence_minutes: int) -> list[dict[str, Any]]:
        """GREY 'offline' records for sites that stopped reporting (probe/node/link down)."""
        out = []
        for site, st in self.sites.items():
            if st.last_seen and now - st.last_seen > timedelta(minutes=silence_minutes):
                out.append({
                    "source": site, "colour": "GREY", "label": "Sensor check", "confidence": 0.0,
                    "wqi": None, "ph": None, "tds": None, "turb": None, "temp": None,
                    "health": "offline", "synthetic": st.synthetic, "latency_ms": 0.0,
                    "updated": now.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                    "ts": now.astimezone(UTC).replace(microsecond=0).isoformat(),
                })  # fmt: skip
        return out


def _num(v: Any) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return f if np.isfinite(f) else float("nan")


# --------------------------------------------------------------------------- service
class Service:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        local = cfg.data_dir / "baselines.json"
        overrides = json.loads(local.read_text(encoding="utf-8")) if local.exists() else {}
        self.engine = EdgeEngine(WaterModel.load(cfg.model_dir), overrides)
        self.outbox = Outbox(cfg.data_dir / "edge.db")
        self.outputs = Outputs(cfg.gpio)
        self.status: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()
        log.info(
            "model loaded: %s, threshold %.3f",
            self.engine.model.meta.get("version"),
            self.engine.model.contam_threshold,
        )

    def handle(self, node: str, reading: dict[str, Any]) -> None:
        site = self.cfg.node_site_map.get(node, node)
        now = datetime.now(UTC).replace(microsecond=0)
        with self.lock:
            self.outbox.log_reading(now, site, reading)
            rec = self.engine.on_reading(site, reading, now)
            if rec:
                self.publish(rec)

    def publish(self, rec: dict[str, Any]) -> None:
        site = rec["source"]
        self.status[site] = rec
        self.outbox.put(rec)
        st = self.engine.sites[site]
        if rec["colour"] == "RED" and time.time() - st.last_alert > self.cfg.alert_repeat_minutes * 60:
            st.last_alert = time.time()
            self.outputs.alarm(True)
            telegram(
                self.cfg, f"RED ALERT {site}: {rec['label']} ({rec['confidence']:.0f}% confidence), WQI {rec['wqi']}"
            )
        if all(s["colour"] != "RED" for s in self.status.values()):
            self.outputs.alarm(False)
        tmp = self.cfg.data_dir / "status.json.tmp"
        tmp.write_text(json.dumps(list(self.status.values()), indent=1), encoding="utf-8")
        os.replace(tmp, self.cfg.data_dir / "status.json")
        with open(self.cfg.data_dir / "latency.csv", "a", encoding="utf-8") as f:
            f.write(f"{int(time.time())},{site},{rec['latency_ms']}\n")
        log.info("%s %s %s %.1f%% WQI %s", site, rec["colour"], rec["label"], rec["confidence"], rec["wqi"])

    def watchdog(self, stop: threading.Event) -> None:
        while not stop.wait(300):
            with self.lock:
                for rec in self.engine.silence_check(datetime.now(UTC), self.cfg.silence_minutes):
                    self.publish(rec)


def parse_line(raw: bytes | str) -> dict[str, Any] | None:
    try:
        text = raw.decode(errors="ignore") if isinstance(raw, bytes) else raw
        text = text.strip()
        return json.loads(text) if text.startswith("{") else None
    except ValueError:
        return None


def run_mqtt(svc: Service) -> None:
    import paho.mqtt.client as mqtt

    def on_message(_c: Any, _u: Any, msg: Any) -> None:
        r = parse_line(msg.payload)
        if r is None:
            return
        node = r.get("node") or r.get("source") or msg.topic.split("/")[1]
        svc.handle(str(node), r)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = lambda c, *_: c.subscribe("wqi/+/reading", qos=1)
    client.on_message = on_message
    client.reconnect_delay_set(1, 60)
    client.connect(svc.cfg.mqtt_host, 1883, 60)
    log.info("listening on mqtt://%s/wqi/+/reading", svc.cfg.mqtt_host)
    client.loop_forever(retry_first_connection=True)


def run_serial(svc: Service, port: str, node: str) -> None:
    import serial  # pyserial

    while True:
        try:
            with serial.Serial(port, 9600, timeout=90) as ser:
                log.info("reading %s", port)
                while True:
                    r = parse_line(ser.readline())
                    if r is not None:
                        svc.handle(str(r.get("node") or node), r)
        except serial.SerialException as exc:
            log.warning("serial error %s; retrying in 10 s", exc)
            time.sleep(10)


def main(argv: list[str] | None = None) -> int:
    load_env(HERE / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serial", help="read the Arduino over USB instead of MQTT, e.g. /dev/ttyACM0")
    ap.add_argument("--node", default="node_01", help="node id for --serial lines without one")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = Config.from_env()
    if not cfg.web_api_key:
        log.warning("WEB_API_KEY not set: records will queue until it is")
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    svc = Service(cfg)
    stop = threading.Event()
    threading.Thread(target=uploader, args=(cfg, svc.outbox, stop), daemon=True).start()
    threading.Thread(target=svc.watchdog, args=(stop,), daemon=True).start()
    try:
        run_serial(svc, args.serial, args.node) if args.serial else run_mqtt(svc)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
    return 0


Reader = Callable[[Service], None]

if __name__ == "__main__":
    raise SystemExit(main())
