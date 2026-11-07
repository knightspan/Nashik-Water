"""Train, evaluate and export the water-state models.

    python -m wqm_ml.train              # full run (~2-4 min), writes models/ and reports/
    python -m wqm_ml.train --quick      # small run for CI

Protocol (no leakage between the three sets):
  * train : 3 independent simulated datasets (seeds 11-13, 21 days each)
  * val   : 1 dataset (seed 21)  -> picks the contamination decision threshold
  * test  : 1 dataset (seed 99)  -> every number in the report
Each dataset is a fresh random realisation of all 7 sites (different weather, events,
faults and start date), so the test set is unseen behaviour, not just unseen minutes.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from . import __version__
from .features import ARDUINO_FEATURES, FEATURES, MIN_HISTORY, PARAMS, add_features, site_baseline, to_windows
from .health import health_series
from .model import CLASSES, EVENT_TO_CLASS, decide
from .synth import generate

ROOT = Path(__file__).resolve().parents[1]
STARTS = ["2026-01-05", "2026-03-02", "2026-06-01", "2026-08-03", "2026-10-05"]
SPLITS = {"train": [11, 12, 13], "val": [21], "test": [99]}


# --------------------------------------------------------------------------- data


def build(seed: int, start: str, days: int) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Generate one dataset -> (1-min raw with health, 5-min feature table, baselines)."""
    raw = generate(days=days, seed=seed, start=start)
    frames, baselines, raw_parts = [], {}, []
    for src, g in raw.groupby("source", sort=False):
        g = g.reset_index(drop=True)
        g["health"] = health_series(g)
        raw_parts.append(g)
        w = to_windows(g[["ts", *PARAMS, "prio"]])
        # A window is classified only if the probe was healthy at its last minute
        # (on the Pi, an unhealthy probe gives GREY "Sensor check" before the model runs).
        h = g.set_index("ts")["health"].resample("5min").last().reindex(w["ts"]).to_numpy()
        w["health"] = h
        b = site_baseline(w)
        f = add_features(w, b).iloc[MIN_HISTORY - 1 :]
        f["source"] = src
        frames.append(f)
        baselines[src] = b
    feats = pd.concat(frames, ignore_index=True)
    feats = feats[(feats["health"] == "ok")].dropna(subset=FEATURES)
    feats["y"] = feats["prio"].map(EVENT_TO_CLASS)
    return pd.concat(raw_parts, ignore_index=True), feats, baselines


def load_split(name: str, days: int, start_offset: int) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    raws, feats, bases = [], [], []
    for i, seed in enumerate(SPLITS[name]):
        r, f, b = build(seed, STARTS[(start_offset + i) % len(STARTS)], days)
        f["seed"] = seed
        r["seed"] = seed
        raws.append(r)
        feats.append(f)
        bases.append(b)
    return pd.concat(raws, ignore_index=True), pd.concat(feats, ignore_index=True), bases


# --------------------------------------------------------------------------- metrics


def class_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, Any]:
    pr, rc, f1, _ = precision_recall_fscore_support(y, p, average="macro", zero_division=0)
    cp, cr, cf, _ = precision_recall_fscore_support(y, p, labels=["Contamination"], zero_division=0)
    per = precision_recall_fscore_support(y, p, labels=CLASSES, zero_division=0)
    return {
        "accuracy": round(accuracy_score(y, p), 4),
        "macro_precision": round(pr, 4),
        "macro_recall": round(rc, 4),
        "macro_f1": round(f1, 4),
        "contam_precision": round(float(cp[0]), 4),
        "contam_recall": round(float(cr[0]), 4),
        "contam_f1": round(float(cf[0]), 4),
        "per_class": {
            c: {
                "precision": round(float(per[0][i]), 3),
                "recall": round(float(per[1][i]), 3),
                "support": int(per[3][i]),
            }
            for i, c in enumerate(CLASSES)
        },
    }


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Start/end (inclusive) indices of consecutive True values."""
    out, start = [], None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        elif not m and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def event_metrics(df: pd.DataFrame, pred: np.ndarray) -> dict[str, Any]:
    """Event-level view: was each contamination episode caught, how fast, and how many
    false RED episodes happened outside real contamination?"""
    df = df.assign(pred=pred)
    delays, missed, false_eps, site_days = [], 0, 0, 0.0
    for _, g in df.groupby(["seed", "source"]):
        g = g.sort_values("ts")
        ts = g["ts"].to_numpy()
        truth = (g["y"] == "Contamination").to_numpy()
        hit = (g["pred"] == "Contamination").to_numpy()
        site_days += (g["ts"].iloc[-1] - g["ts"].iloc[0]).total_seconds() / 86400
        for a, b in runs(truth):
            idx = np.where(hit[a : b + 1])[0]
            if len(idx):
                delays.append((ts[a + idx[0]] - ts[a]) / np.timedelta64(1, "m"))
            else:
                missed += 1
        near = np.convolve(truth.astype(int), np.ones(7, dtype=int), mode="same") > 0  # ±15 min
        for a, b in runs(hit):
            if not near[a : b + 1].any():
                false_eps += 1
    n = len(delays) + missed
    return {
        "events": n,
        "detected": len(delays),
        "missed": missed,
        "detection_rate": round(len(delays) / n, 4) if n else None,
        "mean_delay_min": round(float(np.mean(delays)), 1) if delays else None,
        "median_delay_min": round(float(np.median(delays)), 1) if delays else None,
        "max_delay_min": round(float(np.max(delays)), 1) if delays else None,
        "false_red_episodes": false_eps,
        "false_red_per_site_week": round(false_eps / max(site_days, 1e-9) * 7, 3),
    }


def tune_threshold(
    proba: np.ndarray, classes: list[str], y: np.ndarray, min_precision: float
) -> tuple[float, list[dict[str, float]]]:
    """Lowest-risk threshold: best contamination F1 among thresholds with precision ≥ floor."""
    curve, best = [], (0.5, -1.0)
    for t in np.round(np.arange(0.10, 0.91, 0.025), 3):
        labels, _ = decide(proba, classes, float(t))
        p, r, f, _ = precision_recall_fscore_support(y, labels, labels=["Contamination"], zero_division=0)
        curve.append({"threshold": float(t), "precision": float(p[0]), "recall": float(r[0]), "f1": float(f[0])})
        if p[0] >= min_precision and f[0] > best[1]:
            best = (float(t), float(f[0]))
    return best[0], curve


def health_metrics(raw: pd.DataFrame) -> dict[str, Any]:
    """How well the rules catch the injected faults (minute level)."""
    out = {}
    for fault, verdict in (("dropout", "offline"), ("flatline", "flatline")):
        truth = raw["fault"] == fault
        pred = raw["health"] == verdict
        tp = int((truth & pred).sum())
        out[fault] = {
            "detected_as": verdict,
            "precision": round(tp / max(int(pred.sum()), 1), 3),
            "recall": round(tp / max(int(truth.sum()), 1), 3),
            "minutes": int(truth.sum()),
        }
    clean = raw["fault"].isin(["none", "spike"])
    out["false_flags_on_healthy_minutes_pct"] = round(100 * float((raw.loc[clean, "health"] != "ok").mean()), 3)
    return out


# --------------------------------------------------------------------------- figures


def figures(
    out: Path,
    cm: np.ndarray,
    comparison: list[dict[str, Any]],
    importance: pd.Series,
    curve: list[dict[str, float]],
    thr: float,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted, grid, accent = "#111111", "#6b6a6a", "#e2e2e2", "#0b5cad"
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": muted,
        "axes.labelcolor": ink, "xtick.color": muted, "ytick.color": muted,
        "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 140,
    })  # fmt: skip

    fig, ax = plt.subplots(figsize=(5.4, 4.4))
    norm = cm / cm.sum(axis=1, keepdims=True)
    ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{cm[i, j]:,}\n{norm[i, j]:.1%}", ha="center", va="center",
                    color="white" if norm[i, j] > 0.55 else ink, fontsize=9)  # fmt: skip
    ax.set_xticks(range(3), CLASSES, rotation=15)
    ax.set_yticks(range(3), CLASSES)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title("Random Forest — test set (unseen dataset)", loc="left")
    fig.tight_layout()
    fig.savefig(out / "confusion_matrix_rf.png")
    plt.close(fig)

    metrics = [
        ("macro_f1", "Macro F1"),
        ("contam_recall", "Contamination recall"),
        ("contam_precision", "Contamination precision"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.2), sharey=True)
    names = [c["model"] for c in comparison]
    for ax, (key, title) in zip(axes, metrics, strict=True):
        vals = [c[key] for c in comparison]
        colors = [accent if n.startswith("Random Forest (deployed") else "#9b9a9a" for n in names]
        ax.barh(names, vals, color=colors, height=0.6)
        for i, v in enumerate(vals):
            ax.text(v + 0.01, i, f"{v:.3f}", va="center", fontsize=8, color=ink)
        ax.set_xlim(0, 1.12)
        ax.set_title(title, loc="left", fontsize=10)
        ax.grid(axis="x", color=grid, lw=0.8)
        ax.set_axisbelow(True)
    axes[0].invert_yaxis()
    fig.tight_layout()
    fig.savefig(out / "model_comparison.png")
    plt.close(fig)

    top = importance.sort_values().tail(12)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh(top.index, top.values, color=accent, height=0.6)
    ax.set_title("Random Forest — top 12 features", loc="left")
    ax.grid(axis="x", color=grid, lw=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(out / "feature_importance.png")
    plt.close(fig)

    c = pd.DataFrame(curve)
    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.plot(c.threshold, c.precision, color=ink, lw=2, label="Precision")
    ax.plot(c.threshold, c.recall, color=accent, lw=2, label="Recall")
    ax.axvline(thr, color=muted, ls="--", lw=1)
    ax.text(thr + 0.01, 0.05, f"chosen {thr:.3f}", color=muted, fontsize=8)
    ax.set_xlabel("Contamination probability threshold")
    ax.set_ylim(0, 1.02)
    ax.grid(color=grid, lw=0.8)
    ax.legend(frameon=False, loc="lower left")
    ax.set_title("Threshold chosen on the validation set", loc="left")
    fig.tight_layout()
    fig.savefig(out / "threshold_curve.png")
    plt.close(fig)


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m wqm_ml.train")
    ap.add_argument("--days", type=int, default=21)
    ap.add_argument("--quick", action="store_true", help="small, fast run (CI)")
    ap.add_argument("--min-precision", type=float, default=0.90)
    ap.add_argument("--models", default=str(ROOT / "models"))
    ap.add_argument("--reports", default=str(ROOT / "reports"))
    args = ap.parse_args(argv)
    if args.quick:
        args.days = 10
        SPLITS["train"] = [11]
    models_dir, reports_dir = Path(args.models), Path(args.reports)
    models_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    t_start = time.time()

    print("generating data ...", flush=True)
    _, tr, tr_bases = load_split("train", args.days, 0)
    _, va, _ = load_split("val", args.days, 3)
    te_raw, te, _ = load_split("test", args.days, 4)
    print(f"  windows  train {len(tr):,}  val {len(va):,}  test {len(te):,}", flush=True)

    X, y = tr[FEATURES], tr["y"].to_numpy()
    rf = RandomForestClassifier(
        n_estimators=40 if args.quick else 300,
        min_samples_leaf=2,
        max_features="sqrt",
        class_weight="balanced_subsample",
        n_jobs=-1,
        random_state=42,
    )
    others = {
        "Decision Tree (depth 8)": DecisionTreeClassifier(
            max_depth=8, min_samples_leaf=5, class_weight="balanced", random_state=42
        ),
        "Logistic Regression": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=3000, class_weight="balanced")
        ),
        "Gradient Boosting": HistGradientBoostingClassifier(
            max_iter=60 if args.quick else 300, learning_rate=0.08, class_weight="balanced", random_state=42
        ),
    }

    t0 = time.perf_counter()
    rf.fit(X, y)
    rf_train_s = time.perf_counter() - t0
    classes = list(rf.classes_)

    thr, curve = tune_threshold(rf.predict_proba(va[FEATURES]), classes, va["y"].to_numpy(), args.min_precision)
    print(f"  contamination threshold (val): {thr}", flush=True)

    proba_te = rf.predict_proba(te[FEATURES])
    pred_te, conf_te = decide(proba_te, classes, thr)
    pred_argmax = np.array(classes)[proba_te.argmax(axis=1)]
    y_te = te["y"].to_numpy()

    t0 = time.perf_counter()
    for _ in range(200):
        rf.predict_proba(te[FEATURES].iloc[[0]])
    latency_ms = (time.perf_counter() - t0) / 200 * 1000

    comparison = []
    bundle_path = models_dir / "random_forest.joblib"
    joblib.dump(
        {"model": rf, "features": FEATURES, "contam_threshold": thr, "sklearn": sklearn.__version__},
        bundle_path,
        compress=3,
    )
    comparison.append(
        {
            "model": "Random Forest (deployed, tuned threshold)",
            **class_metrics(y_te, pred_te),
            "train_s": round(rf_train_s, 1),
            "size_kb": round(bundle_path.stat().st_size / 1024),
        }
    )
    comparison.append(
        {
            "model": "Random Forest (argmax)",
            **class_metrics(y_te, pred_argmax),
            "train_s": round(rf_train_s, 1),
            "size_kb": round(bundle_path.stat().st_size / 1024),
        }
    )
    for name, m in others.items():
        t0 = time.perf_counter()
        m.fit(X, y)
        dt = time.perf_counter() - t0
        comparison.append(
            {"model": name, **class_metrics(y_te, m.predict(te[FEATURES])), "train_s": round(dt, 1), "size_kb": None}
        )
        print(f"  {name}: macro F1 {comparison[-1]['macro_f1']}", flush=True)

    deployed = comparison[0]
    events = event_metrics(te, pred_te)
    cm = confusion_matrix(y_te, pred_te, labels=CLASSES)
    correct = pred_te == y_te
    importance = pd.Series(rf.feature_importances_, index=FEATURES)

    # Arduino UNO tree: depth 5 on 6 features it can compute itself.
    ymap = {"Normal": 0, "Natural change": 1, "Contamination": 2}
    edt = DecisionTreeClassifier(max_depth=5, class_weight="balanced", random_state=42)
    edt.fit(tr[ARDUINO_FEATURES], tr["y"].map(ymap))
    ep = edt.predict(te[ARDUINO_FEATURES])
    yt = te["y"].map(ymap).to_numpy()
    arduino = {
        "accuracy": round(accuracy_score(yt, ep), 4),
        "macro_f1": round(precision_recall_fscore_support(yt, ep, average="macro", zero_division=0)[2], 4),
        "alert_recall": round(float(((ep == 2) & (yt == 2)).sum() / max((yt == 2).sum(), 1)), 4),
        "alert_precision": round(float(((ep == 2) & (yt == 2)).sum() / max((ep == 2).sum(), 1)), 4),
        "nodes": int(edt.tree_.node_count),
        "depth": int(edt.get_depth()),
        "features": ARDUINO_FEATURES,
    }
    try:
        from micromlgen import port

        header = port(edt, classname="WaterStateTree", classmap={0: "NORMAL", 1: "NATURAL", 2: "ALERT"})
        (models_dir / "WaterStateTree.h").write_text(header, encoding="utf-8")
        arduino["header_kb"] = round(len(header.encode()) / 1024, 1)
    except ImportError:
        print("  micromlgen not installed: skipping Arduino header", flush=True)

    # Deployment baselines: median over the training realisations.
    site_baseline_out = {
        s: {p: round(float(np.median([b[s][p] for b in tr_bases])), 3) for p in ("ph", "tds", "turb")}
        for s in tr_bases[0]
    }

    metrics = {
        "version": __version__,
        "sklearn": sklearn.__version__,
        "protocol": {"days_per_dataset": args.days, "splits": SPLITS, "quick": args.quick},
        "windows": {"train": len(tr), "val": len(va), "test": len(te)},
        "class_counts_test": te["y"].value_counts().to_dict(),
        "contam_threshold": thr,
        "deployed": deployed,
        "events": events,
        "confidence": {
            "mean": round(float(conf_te.mean()), 1),
            "correct_mean": round(float(conf_te[correct].mean()), 1),
            "wrong_mean": round(float(conf_te[~correct].mean()), 1) if (~correct).any() else None,
        },
        "latency_ms_single_prediction_this_pc": round(latency_ms, 2),
        "comparison": comparison,
        "top_features": importance.sort_values(ascending=False).head(8).round(4).to_dict(),
        "health_rules": health_metrics(te_raw),
        "arduino_tree": arduino,
        "confusion_matrix": {"labels": CLASSES, "matrix": cm.tolist()},
        "threshold_curve": curve,
        "runtime_s": round(time.time() - t_start, 1),
    }
    meta = {
        "version": __version__,
        "sklearn": sklearn.__version__,
        "features": FEATURES,
        "classes": classes,
        "contam_threshold": thr,
        "min_history_windows": MIN_HISTORY,
        "site_baseline": site_baseline_out,
        "test_metrics": {k: deployed[k] for k in ("accuracy", "macro_f1", "contam_precision", "contam_recall")},
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (models_dir / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    (reports_dir / "metrics.json").write_text(json.dumps(metrics, indent=1, default=str), encoding="utf-8")
    write_arduino_baseline(models_dir, site_baseline_out["ramkund"])
    figures(reports_dir, cm, comparison, importance, curve, thr)
    write_report(reports_dir, metrics)

    print(json.dumps({k: metrics[k] for k in ("contam_threshold", "events", "confidence", "runtime_s")}, indent=1))
    print(json.dumps({k: deployed[k] for k in ("accuracy", "macro_f1", "contam_precision", "contam_recall")}, indent=1))
    return 0


def write_arduino_baseline(models_dir: Path, b: dict[str, float]) -> None:
    (models_dir / "SiteBaseline.h").write_text(
        "// Generated by wqm_ml.train - baseline of the site this node is installed at.\n"
        "// Replace with values from edge/calibrate_baseline.py after a week of real logging.\n"
        "#pragma once\n"
        f"const float BASE_PH = {b['ph']:.3f};\n"
        f"const float BASE_TDS = {b['tds']:.1f};\n"
        f"const float BASE_TURB = {b['turb']:.2f};\n",
        encoding="utf-8",
    )


def write_report(reports_dir: Path, m: dict[str, Any]) -> None:
    d, ev, a, h = m["deployed"], m["events"], m["arduino_tree"], m["health_rules"]
    rows = "\n".join(
        f"| {c['model']} | {c['accuracy']:.3f} | {c['macro_f1']:.3f} | {c['contam_precision']:.3f} | {c['contam_recall']:.3f} | {c['train_s']} |"
        for c in m["comparison"]
    )
    per = "\n".join(
        f"| {k} | {v['precision']:.3f} | {v['recall']:.3f} | {v['support']:,} |" for k, v in d["per_class"].items()
    )
    feats = "\n".join(f"| `{k}` | {v:.3f} |" for k, v in m["top_features"].items())
    text = f"""# Model report

Generated by `python -m wqm_ml.train` (wqm_ml {m['version']}, scikit-learn {m['sklearn']}).
All numbers are on the **test dataset (seed 99)**, a fresh simulated realisation of all 7
sites that was never used for training or for choosing the threshold.

> These results are on simulated data built from the team's field-test baselines. They show
> the method works; performance on the real Ramkund probe must be confirmed with months of
> real logging (see docs/HARDWARE.md, "Validation").

## Deployed model: Random Forest + tuned contamination threshold

| Metric | Value |
|---|---|
| Accuracy | {d['accuracy']:.3f} |
| Macro F1 | {d['macro_f1']:.3f} |
| Contamination precision | {d['contam_precision']:.3f} |
| Contamination recall (5-min windows) | {d['contam_recall']:.3f} |
| Contamination events caught | {ev['detected']} of {ev['events']} ({(ev['detection_rate'] or 0):.1%}) |
| Detection delay (mean / median / max) | {ev['mean_delay_min']} / {ev['median_delay_min']} / {ev['max_delay_min']} min |
| False RED episodes | {ev['false_red_episodes']} ({ev['false_red_per_site_week']} per site per week) |
| Contamination threshold (from validation set) | {m['contam_threshold']} |
| Mean confidence (correct / wrong) | {m['confidence']['correct_mean']}% / {m['confidence']['wrong_mean']}% |
| Prediction latency, one window (this PC) | {m['latency_ms_single_prediction_this_pc']} ms |

Windows: train {m['windows']['train']:,} · validation {m['windows']['val']:,} · test {m['windows']['test']:,}.

### Per class

| Class | Precision | Recall | Test windows |
|---|---|---|---|
{per}

![Confusion matrix](confusion_matrix_rf.png)

## Model comparison (same test set)

| Model | Accuracy | Macro F1 | Contam. precision | Contam. recall | Train (s) |
|---|---|---|---|---|---|
{rows}

![Model comparison](model_comparison.png)

## What changed from the first version (WQM_code/pi/analysis.py)

1. **Causal features.** The Hampel filter used a centred window (it looked 25 minutes into
   the future), which the Pi cannot do live. Windows are now the median of the 1-minute
   readings, and every feature uses past data only — training and the Pi compute identical values.
2. **Labels follow the water.** An event is labelled only while its signal is ≥ 15 % of its
   peak, not for a fixed 2-hour tail after it. The old tail labels asked the model to call
   already-clean water "Contamination", which capped recall around 0.72.
3. **Faster onset features** (`d1_*`, the 5-minute change) shorten the detection delay.
4. **Threshold tuned on a separate validation set** with a precision floor of 0.90, so
   recall rises without a flood of false RED alarms.
5. **Honest evaluation.** Test data is a different random realisation, and sensor-fault
   windows are removed (on the Pi they become GREY "Sensor check" before the model runs).

## Most important features

| Feature | Importance |
|---|---|
{feats}

![Feature importance](feature_importance.png)
![Threshold curve](threshold_curve.png)

## Sensor-health rules (minute level, test set)

| Fault | Detected as | Precision | Recall | Minutes |
|---|---|---|---|---|
| dropout | {h['dropout']['detected_as']} | {h['dropout']['precision']} | {h['dropout']['recall']} | {h['dropout']['minutes']:,} |
| flatline | {h['flatline']['detected_as']} | {h['flatline']['precision']} | {h['flatline']['recall']} | {h['flatline']['minutes']:,} |

Healthy minutes wrongly flagged: {h['false_flags_on_healthy_minutes_pct']} %.

## Arduino UNO decision tree (offline local alerts)

Depth {a['depth']}, {a['nodes']} nodes, {a.get('header_kb', '?')} KB header, features {', '.join(f'`{f}`' for f in a['features'])}.
Accuracy {a['accuracy']:.3f}, macro F1 {a['macro_f1']:.3f}, ALERT recall {a['alert_recall']:.3f}, ALERT precision {a['alert_precision']:.3f}.
Copy `ml/models/WaterStateTree.h` and `ml/models/SiteBaseline.h` into `firmware/arduino_node/`.
"""
    (reports_dir / "REPORT.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
