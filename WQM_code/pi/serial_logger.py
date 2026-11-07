#!/usr/bin/env python3
"""serial_logger.py - Assignment 2.5/2.6: save Arduino JSON readings to CSV.
Usage: python serial_logger.py COM5 godavari_ramkund 120    (port, source name, number of readings)
"""
import csv, json, sys, time
from datetime import datetime
import serial

port, source, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
ser = serial.Serial(port, 9600, timeout=90)
time.sleep(2)                                    # the UNO resets when the port opens
fname = f"readings_{source}_{datetime.now():%Y%m%d_%H%M}.csv"
with open(fname, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["timestamp", "source", "ph", "tds_mg_l", "turbidity_ntu", "temperature_c", "temp_ok", "edge_state"])
    count = 0
    while count < n:
        line = ser.readline().decode(errors="ignore").strip()
        if not line.startswith("{"):
            print(line); continue                 # start-up message
        r = json.loads(line)
        w.writerow([datetime.now().isoformat(timespec="seconds"), source, r["ph"], r["tds"], r["turb"],
                    r["temp"], r["temp_ok"], r["edge_state"]])
        f.flush(); count += 1
        print(f"{count:3d}/{n}  pH {r['ph']:.2f}  TDS {r['tds']:.0f}  NTU {r['turb']:.1f}  T {r['temp']:.1f}")
print("saved", fname)
