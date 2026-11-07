#!/usr/bin/env python3
"""edge_ai.py - real-time AI on the Raspberry Pi 5.
Every 5 minutes, for every source: build the same features used in training, run the
Random Forest water-state classifier and the sensor-health checks, decide the public
status (GREEN / AMBER / RED / GREY), drive the buzzer, LED and relay, send Telegram
alerts and upload the status of every site to the hosted website back end.
"""
import json, os, time, queue, threading
from collections import defaultdict, deque
import joblib, numpy as np, pandas as pd, requests
import paho.mqtt.client as mqtt
from gpiozero import LED, Buzzer, OutputDevice

RF = joblib.load("models/random_forest.joblib")
META = json.load(open("models/meta.json"))          # feature list + site baselines
FEAT, BASE = META["features"], META["site_baseline"]
buzzer, led, relay = Buzzer(17), LED(27), OutputDevice(22, active_high=False)
win = defaultdict(lambda: deque(maxlen=200))          # last 200 minutes per source
hist5 = defaultdict(lambda: deque(maxlen=80))         # 5-minute means per source
status, last_alert = {}, defaultdict(float)
API_URL = os.environ.get("WEB_API_URL", "https://<your-backend>.onrender.com") + "/api/ingest"
API_KEY = os.environ.get("WEB_API_KEY", "")
outbox = queue.Queue()                                # survives short internet outages


def uploader():
    """Send status records to the website back end; retry while offline."""
    while True:
        rec = outbox.get()
        while True:
            try:
                r = requests.post(API_URL, json=rec, headers={"X-API-Key": API_KEY}, timeout=10)
                if r.status_code < 500: break
            except requests.RequestException:
                pass
            time.sleep(30)
SI = {"ph": 8.5, "tds": 500.0, "turb": 5.0}
W = {k: (1 / v) / sum(1 / x for x in SI.values()) for k, v in SI.items()}


def wqi(ph, tds, turb):
    q = 100 * (ph - 7) / 1.5 if ph >= 7 else 100 * (7 - ph) / 0.5
    return W["ph"] * q + W["tds"] * 100 * tds / 500 + W["turb"] * 100 * turb / 5


def telegram(text):
    tok, chat = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT")
    if tok and chat:
        try: requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", data={"chat_id": chat, "text": text}, timeout=5)
        except requests.RequestException: pass      # local alerts still work offline


def sensor_health(rows):
    df = pd.DataFrame(rows)
    if len(df) < 10 or df[["ph", "tds", "turb"]].isna().any(axis=1).tail(5).all(): return "offline"
    if (df[["ph", "tds", "turb"]].tail(30).std() < 1e-4).any(): return "flatline"
    if not df.ph.between(2, 12).all(): return "out_of_range"
    return "ok"


def features(src):
    h = pd.DataFrame(hist5[src])
    if len(h) < 75: return None                        # needs 6 h of history for baselines
    g = h.copy()
    for p in ["ph", "tds", "turb", "temp"]:
        g[f"d_{p}"] = g[p].diff(3); g[f"sd_{p}"] = g[p].rolling(6, min_periods=3).std()
    for p, e in (("ph", 0.1), ("tds", 10), ("turb", 1)):
        base = g[p].shift(6).rolling(72, min_periods=24).median(); g[f"dev_{p}"] = (g[p] - base) / (base.abs() + e)
    hr = time.localtime().tm_hour + time.localtime().tm_min / 60
    g["h_sin"], g["h_cos"] = np.sin(2 * np.pi * hr / 24), np.cos(2 * np.pi * hr / 24)
    b = BASE.get(src, {"ph": g.ph.median(), "tds": g.tds.median(), "turb": g.turb.median()})
    g["rel_ph"], g["rel_tds"] = g.ph - b["ph"], g.tds / b["tds"]
    g["rel_turb"] = (g.turb + 0.5) / (b["turb"] + 0.5)
    return g[FEAT].iloc[[-1]]


def evaluate(src):
    rows = list(win[src])[-5:]
    m = {k: float(np.nanmean([r[k] for r in rows])) for k in ("ph", "tds", "turb", "temp")}
    m["wqi"] = wqi(m["ph"], m["tds"], m["turb"]); hist5[src].append(m)
    health = sensor_health(list(win[src]))
    x = features(src); t0 = time.perf_counter()
    if health != "ok": label, conf, colour = "Sensor check", 0.0, "GREY"
    elif x is None: label, conf, colour = "Learning baseline", 0.0, "GREY"
    else:
        p = RF.predict_proba(x)[0]; i = int(np.argmax(p)); label, conf = RF.classes_[i], float(p[i])
        colour = {"Normal": "GREEN", "Natural change": "AMBER", "Contamination": "RED"}[label]
    ms = (time.perf_counter() - t0) * 1000
    status[src] = dict(source=src, colour=colour, label=label, confidence=round(conf * 100, 1),
                       wqi=round(m["wqi"], 1), **{k: round(v, 2) for k, v in m.items() if k != "wqi"},
                       health=health, latency_ms=round(ms, 2), synthetic=rows[-1].get("synthetic", False),
                       updated=time.strftime("%Y-%m-%d %H:%M:%S"))
    if colour == "RED" and time.time() - last_alert[src] > 1800:
        buzzer.beep(0.3, 0.2, n=3, background=True); led.on(); relay.on(); last_alert[src] = time.time()
        telegram(f"RED ALERT {src}: {label} ({conf*100:.0f}% confidence), WQI {m['wqi']:.0f}")
    if all(s["colour"] != "RED" for s in status.values()): led.off(); relay.off()
    json.dump(list(status.values()), open("data/status.json.tmp", "w")); os.replace("data/status.json.tmp", "data/status.json")
    outbox.put(status[src])                           # -> hosted website back end
    with open("logs/latency.csv", "a") as f: f.write(f"{int(time.time())},{src},{ms:.3f}\n")


def on_message(client, userdata, msg):
    r = json.loads(msg.payload); src = r.get("node") or r.get("source")
    win[src].append(r)
    if len(win[src]) % 5 == 0: evaluate(src)


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True); os.makedirs("data", exist_ok=True)
    threading.Thread(target=uploader, daemon=True).start()
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.on_connect = lambda cl, u, f, rc, p: cl.subscribe("wqi/+/reading")
    c.on_message = on_message; c.connect("localhost", 1883, 60); c.loop_forever()
