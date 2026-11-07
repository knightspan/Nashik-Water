#!/usr/bin/env python3
"""latency_test.py - Assignment 7.4/7.5: edge (Pi 5) vs cloud inference latency."""
import json, statistics, time
import joblib, numpy as np, requests

CLOUD = "http://<cloud-or-laptop-address>:8000/predict"
rf = joblib.load("models/random_forest.joblib"); feats = json.load(open("models/meta.json"))["features"]
x = np.random.rand(1, len(feats))


def edge():
    t = time.perf_counter(); rf.predict_proba(x); return (time.perf_counter() - t) * 1000


def cloud():
    t = time.perf_counter(); requests.post(CLOUD, json={"x": x[0].tolist()}, timeout=10).raise_for_status()
    return (time.perf_counter() - t) * 1000


for name, fn in (("edge", edge), ("cloud", cloud)):
    ts = sorted(fn() for _ in range(100))
    print(f"{name}: mean {statistics.mean(ts):.1f} ms, median {statistics.median(ts):.1f} ms, p95 {ts[94]:.1f} ms")
