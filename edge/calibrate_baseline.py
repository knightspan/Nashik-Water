#!/usr/bin/env python3
"""calibrate_baseline.py — learn a site's "normal" from a week of real readings.

The model compares each window with the site's baseline (rel_ph, rel_tds, rel_turb).
The shipped baselines come from simulated data; after installing the real probe, log a
quiet week and run this to replace them with the probe's own values.

    python calibrate_baseline.py --site ramkund --days 7            # from data/edge.db
    python calibrate_baseline.py --site ramkund --csv readings.csv  # from serial_logger CSV

Writes/updates data/baselines.json (picked up by edge_ai.py on restart) and prints the
three values to paste into firmware/arduino_node/SiteBaseline.h.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--days", type=float, default=7)
    ap.add_argument("--csv", help="CSV with columns ph, tds/tds_mg_l, turb/turbidity_ntu")
    ap.add_argument("--data-dir", default=str(HERE / "data"))
    args = ap.parse_args()
    data_dir = Path(args.data_dir)

    if args.csv:
        df = pd.read_csv(args.csv).rename(columns={"tds_mg_l": "tds", "turbidity_ntu": "turb"})
    else:
        con = sqlite3.connect(data_dir / "edge.db")
        df = pd.read_sql_query(
            "SELECT * FROM readings WHERE site = ? AND ts >= datetime('now', ?)",
            con,
            params=(args.site, f"-{args.days} days"),
        )
    df = df.dropna(subset=["ph", "tds", "turb"])
    if len(df) < 60 * 24:
        print(f"Only {len(df)} readings: log at least a full day (ideally a week) of quiet water.")
        return 1
    # 5-minute medians, then the median of those: robust to bathing peaks and spikes.
    base = {p: round(float(df[p].rolling(5).median().median()), 3) for p in ("ph", "tds", "turb")}

    path = data_dir / "baselines.json"
    all_b = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    all_b[args.site] = base
    path.write_text(json.dumps(all_b, indent=1), encoding="utf-8")
    print(f"{args.site}: {base}  -> {path}")
    print(
        f"SiteBaseline.h:\n  const float BASE_PH = {base['ph']:.3f};\n"
        f"  const float BASE_TDS = {base['tds']:.1f};\n  const float BASE_TURB = {base['turb']:.2f};"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
