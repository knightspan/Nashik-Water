#!/usr/bin/env python3
"""ingest_store.py - subscribe to every node (real and virtual) and store readings in SQLite.
Run on the Raspberry Pi 5:  python ingest_store.py
Export CSV:  sqlite3 -header -csv data/wqi.db "SELECT * FROM readings" > data/readings.csv
"""
import json, os, sqlite3, time
import paho.mqtt.client as mqtt

os.makedirs("data", exist_ok=True)
db = sqlite3.connect("data/wqi.db", check_same_thread=False)
db.execute("""CREATE TABLE IF NOT EXISTS readings(
    epoch INTEGER, source TEXT, ph REAL, tds REAL, turb REAL, temp REAL,
    edge_state INTEGER, synthetic INTEGER)""")
db.commit()


def on_message(client, userdata, msg):
    try:
        r = json.loads(msg.payload)
    except ValueError:
        return                                   # ignore malformed lines
    src = r.get("node") or r.get("source")
    db.execute("INSERT INTO readings VALUES (?,?,?,?,?,?,?,?)",
               (int(r.get("epoch", time.time())), src, r.get("ph"), r.get("tds"), r.get("turb"),
                r.get("temp"), r.get("edge_state"), int(bool(r.get("synthetic", False)))))
    db.commit()


c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
c.on_connect = lambda cl, u, f, rc, p: cl.subscribe("wqi/+/reading")
c.on_message = on_message
c.connect("localhost", 1883, 60)
c.loop_forever()
