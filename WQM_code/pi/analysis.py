#!/usr/bin/env python3
"""analysis.py - Assignments 4-7: cleaning, statistics, plots, ML models, edge export.

Input : data/synthetic_1min.csv  (from synth_water.py, 7 sources, seed 42)
Output: figs/*.png, results/results.json, results/*.csv, models/*
"""
import json, os, time
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import (accuracy_score, precision_recall_fscore_support,
                             confusion_matrix, classification_report)

os.makedirs("figs", exist_ok=True); os.makedirs("results", exist_ok=True); os.makedirs("models", exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "figure.dpi": 130})
R = {}
PARAMS = ["ph", "tds", "turb", "temp"]
LBL = {"ph": "pH", "tds": "TDS (mg/L)", "turb": "Turbidity (NTU)", "temp": "Temperature (°C)"}
NICE = {"ugamsthan_trimbakeshwar": "Ugamsthan", "kushavart": "Kushavart", "someshwar": "Someshwar",
        "gangapur_dam": "Gangapur Dam", "ramkund": "Ramkund", "tapovan": "Tapovan", "nandini": "Nandini"}
SI = {"ph": 8.5, "tds": 500.0, "turb": 5.0}
_inv = {k: 1 / v for k, v in SI.items()}; W = {k: v / sum(_inv.values()) for k, v in _inv.items()}


def wqi(ph, tds, turb):
    ph = np.asarray(ph, float)
    q = np.where(ph >= 7, 100 * (ph - 7) / 1.5, 100 * (7 - ph) / 0.5)
    return W["ph"] * q + W["tds"] * 100 * np.asarray(tds) / 500 + W["turb"] * 100 * np.asarray(turb) / 5


# ------------------------------------------------------------ Assignment 4
raw = pd.read_csv("data/synthetic_1min.csv")
raw["ts"] = pd.to_datetime(raw["epoch"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
R["raw_rows"] = int(len(raw)); R["sources"] = int(raw.source.nunique())
R["days"] = round((raw.epoch.max() - raw.epoch.min()) / 86400, 1)
R["raw_missing"] = {p: int(raw[p].isna().sum()) for p in PARAMS}
R["duplicates"] = int(raw.duplicated(["source", "epoch"]).sum())
R["events"] = raw.groupby("event").size().to_dict()
R["faults"] = raw.groupby("fault").size().to_dict()

RANGES = {"ph": (0, 14), "tds": (0, 2000), "turb": (0, 3000), "temp": (0, 50)}
FLOOR = {"ph": 0.02, "tds": 2.0, "turb": 0.5, "temp": 0.05}


def hampel(s, floor, window=11, k=3.0):
    med = s.rolling(window, center=True, min_periods=3).median()
    mad = (s - med).abs().rolling(window, center=True, min_periods=3).median()
    sig = (1.4826 * mad).clip(lower=floor)
    return s.mask((s - med).abs() > k * sig)


PRIO = {"normal": 0, "rain": 1, "bathing": 2, "contamination": 4}
removed = {p: 0 for p in PARAMS}
clean_parts, example = [], None
for src, g in raw.groupby("source"):
    g = g.sort_values("ts").set_index("ts").copy()
    for p in PARAMS:
        before = g[p].copy()
        g[p] = hampel(g[p].where(g[p].between(*RANGES[p])), FLOOR[p])
        removed[p] += int(g[p].isna().sum() - before.isna().sum())
        if src == "ramkund" and p == "tds":
            example = (before, g[p].copy())
    g["prio"] = g["event"].map(PRIO)
    agg = g[PARAMS].resample("5min").mean()
    agg["prio"] = g["prio"].resample("5min").max()
    agg["fault"] = g["fault"].resample("5min").agg(lambda x: x.mode().iloc[0] if len(x) else "none")
    agg[PARAMS] = agg[PARAMS].interpolate(method="time", limit=3, limit_area="inside")
    agg = agg.dropna(subset=PARAMS)
    agg["source"] = src
    clean_parts.append(agg)
clean = pd.concat(clean_parts).reset_index()
inv = {v: k for k, v in PRIO.items()}
clean["event"] = clean["prio"].map(inv)
clean["wqi"] = wqi(clean.ph, clean.tds, clean.turb)
R["hampel_removed"] = removed
R["clean_rows"] = int(len(clean))
clean.to_csv("results/clean_5min.csv", index=False)

stats = clean.groupby("source")[PARAMS + ["wqi"]].agg(["mean", "median", "std", "min", "max"]).round(2)
stats.to_csv("results/stats_per_source.csv")
R["stats"] = {s: {p: {m: float(stats.loc[s, (p, m)]) for m in ["mean", "median", "std", "min", "max"]}
                  for p in PARAMS + ["wqi"]} for s in stats.index}
band = pd.cut(clean.wqi, [-1, 25, 50, 75, 100, 1e9], labels=["Excellent", "Good", "Poor", "Very poor", "Unfit"])
R["band_share"] = (pd.crosstab(clean.source, band, normalize="index") * 100).round(1).to_dict(orient="index")

# Fig 4.x  before/after Hampel
b, a = example
sl = slice(b.index[3000], b.index[3000 + 720])
fig, ax = plt.subplots(figsize=(9, 3.2))
ax.plot(b[sl].index, b[sl].values, color="#d9534f", lw=0.8, label="Raw (with spikes)")
ax.plot(a[sl].index, a[sl].values, color="#1f5fa8", lw=1.0, label="After Hampel filter")
ax.set_ylabel("TDS (mg/L)"); ax.set_title("Outlier removal – Ramkund, 12 h of 1-minute TDS data")
ax.legend(); fig.autofmt_xdate(); fig.tight_layout(); fig.savefig("figs/a4_hampel.png"); plt.close()

# missing / removed bar
fig, ax = plt.subplots(figsize=(7, 3))
x = np.arange(4)
ax.bar(x - 0.2, [R["raw_missing"][p] for p in PARAMS], 0.4, label="Missing (dropouts)", color="#888")
ax.bar(x + 0.2, [removed[p] - R["raw_missing"][p] * 0 for p in PARAMS], 0.4, label="Removed as outliers / invalid", color="#d9534f")
ax.set_xticks(x); ax.set_xticklabels([LBL[p] for p in PARAMS]); ax.set_ylabel("Readings")
ax.set_title("Missing and removed readings per parameter"); ax.legend(); fig.tight_layout()
fig.savefig("figs/a4_missing.png"); plt.close()

# time series 7 days, 4 sources
show = ["ugamsthan_trimbakeshwar", "kushavart", "ramkund", "nandini"]
fig, axes = plt.subplots(4, 1, figsize=(10, 9), sharex=False)
for ax, s in zip(axes, show):
    g = clean[clean.source == s].iloc[: 7 * 288]
    ax.plot(g.ts, g.turb, color="#1f77b4", lw=0.8); ax.set_ylabel("Turb (NTU)", color="#1f77b4")
    ax2 = ax.twinx(); ax2.plot(g.ts, g.tds, color="#d62728", lw=0.8); ax2.set_ylabel("TDS (mg/L)", color="#d62728")
    ax.set_title(NICE[s], fontsize=10)
fig.suptitle("Turbidity and TDS over 7 days (5-minute cleaned data)"); fig.tight_layout()
fig.savefig("figs/a4_timeseries.png"); plt.close()

# box plot WQI
order = clean.groupby("source").wqi.median().sort_values().index
fig, ax = plt.subplots(figsize=(9, 3.8))
sns.boxplot(data=clean, x="source", y="wqi", order=order, ax=ax, showfliers=False, color="#9ecae1")
ax.axhline(50, color="red", ls="--", lw=1, label="Alert limit (WQI 50)")
ax.set_xticklabels([NICE[s] for s in order], rotation=20); ax.set_xlabel(""); ax.set_ylabel("WQI")
ax.set_yscale("log"); ax.legend(); ax.set_title("WQI distribution per source (log scale, raw surface water)")
fig.tight_layout(); fig.savefig("figs/a4_boxplot.png"); plt.close()

# correlation heatmap
fig, ax = plt.subplots(figsize=(5.5, 4.5))
sns.heatmap(clean[PARAMS + ["wqi"]].corr().round(2), annot=True, cmap="coolwarm", vmin=-1, vmax=1, ax=ax,
            xticklabels=["pH", "TDS", "Turb", "Temp", "WQI"], yticklabels=["pH", "TDS", "Turb", "Temp", "WQI"])
ax.set_title("Correlation between parameters"); fig.tight_layout(); fig.savefig("figs/a4_corr.png"); plt.close()
R["corr"] = clean[PARAMS + ["wqi"]].corr().round(2).to_dict()

# diurnal temperature
fig, ax = plt.subplots(figsize=(8, 3.2))
for s in ["ugamsthan_trimbakeshwar", "ramkund", "nandini"]:
    g = clean[clean.source == s]
    h = g.groupby(g.ts.dt.hour).temp.mean(); ax.plot(h.index, h.values, marker="o", ms=3, label=NICE[s])
ax.set_xlabel("Hour of day"); ax.set_ylabel("Mean temperature (°C)"); ax.legend()
ax.set_title("Daily temperature pattern"); fig.tight_layout(); fig.savefig("figs/a4_diurnal.png"); plt.close()

# mean bars per source
fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
for ax, p in zip(axes, ["ph", "tds", "turb"]):
    m = clean.groupby("source")[p].mean().reindex(order)
    ax.bar([NICE[s] for s in order], m.values, color="#4c9bd6")
    ax.set_title("Mean " + LBL[p]); ax.tick_params(axis="x", rotation=60, labelsize=8)
fig.tight_layout(); fig.savefig("figs/a4_means.png"); plt.close()

# ------------------------------------------------------------ features
def feats(g):
    g = g.sort_values("ts").copy()
    for p in ["ph", "tds", "turb", "temp"]:
        g[f"d_{p}"] = g[p].diff(3)                                    # change over 15 min
        g[f"sd_{p}"] = g[p].rolling(6, min_periods=3).std()            # variability over 30 min
    for p in ["ph", "tds", "turb"]:
        base = g[p].shift(6).rolling(72, min_periods=24).median()      # 6 h baseline, past only
        g[f"dev_{p}"] = (g[p] - base) / (base.abs() + {"ph": 0.1, "tds": 10, "turb": 1}[p])
    h = g.ts.dt.hour + g.ts.dt.minute / 60
    g["h_sin"], g["h_cos"] = np.sin(2 * np.pi * h / 24), np.cos(2 * np.pi * h / 24)
    return g


F = pd.concat([feats(g) for _, g in clean.groupby("source")]).dropna()
FEAT = ["ph", "tds", "turb", "temp", "wqi", "d_ph", "d_tds", "d_turb", "d_temp", "sd_ph", "sd_tds",
        "sd_turb", "sd_temp", "dev_ph", "dev_tds", "dev_turb", "h_sin", "h_cos"]
cls_map = {"normal": "Normal", "rain": "Natural change", "bathing": "Natural change",
           "contamination": "Contamination"}
F["y"] = F.event.map(cls_map)
CLASSES = ["Normal", "Natural change", "Contamination"]

# site baseline: each node learns its own "normal" from its first (training) period
tr, te = [], []
BASE = {}
for s, g in F.groupby("source"):
    n = len(g); a, b = g.iloc[: int(0.7 * n)].copy(), g.iloc[int(0.7 * n):].copy()
    nb = a[a.y == "Normal"]
    BASE[s] = {"ph": float(nb.ph.median()), "tds": float(nb.tds.median()), "turb": float(nb.turb.median())}
    for d in (a, b):
        d["rel_ph"] = d.ph - BASE[s]["ph"]
        d["rel_tds"] = d.tds / BASE[s]["tds"]
        d["rel_turb"] = (d.turb + 0.5) / (BASE[s]["turb"] + 0.5)
    tr.append(a); te.append(b)
TR, TE = pd.concat(tr), pd.concat(te)
FEAT += ["rel_ph", "rel_tds", "rel_turb"]
R["site_baseline"] = {k: {p: round(v, 2) for p, v in d.items()} for k, d in BASE.items()}
R["n_train"], R["n_test"] = int(len(TR)), int(len(TE))
R["class_train"] = TR.y.value_counts().to_dict(); R["class_test"] = TE.y.value_counts().to_dict()
R["n_features"] = len(FEAT)

# ------------------------------------------------------------ Assignment 5
models = {
    "Decision Tree": DecisionTreeClassifier(max_depth=6, class_weight="balanced", random_state=42),
    "Random Forest": RandomForestClassifier(n_estimators=100, min_samples_leaf=5, class_weight="balanced",
                                            n_jobs=-1, random_state=42),
    "Logistic Regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, class_weight="balanced")),
}
res, preds = [], {}
for name, m in models.items():
    t0 = time.perf_counter(); m.fit(TR[FEAT], TR.y); tt = time.perf_counter() - t0
    p = m.predict(TE[FEAT]); preds[name] = p
    pr, rc, f1, _ = precision_recall_fscore_support(TE.y, p, average="macro", zero_division=0)
    prc, rcc, f1c, _ = precision_recall_fscore_support(TE.y, p, labels=["Contamination"], zero_division=0)
    joblib.dump(m, f"models/{name.lower().replace(' ', '_')}.joblib")
    res.append(dict(model=name, accuracy=accuracy_score(TE.y, p), macro_precision=pr, macro_recall=rc, macro_f1=f1,
                    contam_precision=prc[0], contam_recall=rcc[0], contam_f1=f1c[0], train_s=tt,
                    size_kb=os.path.getsize(f"models/{name.lower().replace(' ', '_')}.joblib") / 1024))
    cm = confusion_matrix(TE.y, p, labels=CLASSES)
    fig, ax = plt.subplots(figsize=(5.2, 4.3))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=CLASSES, yticklabels=CLASSES, ax=ax, cbar=False)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title(f"Confusion matrix – {name}")
    plt.xticks(rotation=25, ha="right"); fig.tight_layout()
    fig.savefig(f"figs/a5_cm_{name.lower().replace(' ', '_')}.png"); plt.close()
    R.setdefault("reports", {})[name] = classification_report(TE.y, p, labels=CLASSES, output_dict=True, zero_division=0)
resdf = pd.DataFrame(res).round(3); resdf.to_csv("results/model_comparison.csv", index=False)
R["model_comparison"] = resdf.to_dict(orient="records")

fig, ax = plt.subplots(figsize=(8, 3.6))
mets = ["accuracy", "macro_precision", "macro_recall", "macro_f1", "contam_recall"]
x = np.arange(len(mets))
for i, r in enumerate(res):
    ax.bar(x + (i - 1) * 0.27, [r[k] for k in mets], 0.27, label=r["model"])
ax.set_xticks(x); ax.set_xticklabels(["Accuracy", "Macro precision", "Macro recall", "Macro F1", "Contamination recall"])
ax.set_ylim(0, 1.15); ax.legend(loc="upper center", ncol=3, fontsize=8); ax.set_title("Model comparison on the test set")
fig.tight_layout(); fig.savefig("figs/a5_comparison.png"); plt.close()

rf = models["Random Forest"]
imp = pd.Series(rf.feature_importances_, index=FEAT).sort_values()
fig, ax = plt.subplots(figsize=(6.5, 4.8)); imp.plot.barh(ax=ax, color="#4c9bd6")
ax.set_title("Random Forest feature importance"); fig.tight_layout(); fig.savefig("figs/a5_importance.png"); plt.close()
R["top_features"] = imp.sort_values(ascending=False).head(6).round(3).to_dict()

# class distribution figure
fig, ax = plt.subplots(figsize=(6.5, 3))
vc = F.y.value_counts().reindex(CLASSES)
ax.bar(CLASSES, vc.values, color=["#5cb85c", "#5bc0de", "#d9534f"])
for i, v in enumerate(vc.values): ax.text(i, v, str(v), ha="center", va="bottom", fontsize=9)
ax.set_yscale("log"); ax.set_ylabel("5-min windows (log)"); ax.set_title("Class distribution of the labelled dataset")
fig.tight_layout(); fig.savefig("figs/a5_classes.png"); plt.close()
R["class_all"] = vc.to_dict()

# Isolation Forest (unsupervised, trained on normal windows only)
AF = ["d_ph", "d_tds", "d_turb", "sd_ph", "sd_tds", "sd_turb", "dev_ph", "dev_tds", "dev_turb", "rel_ph", "rel_tds", "rel_turb"]
iso = make_pipeline(StandardScaler(), IsolationForest(n_estimators=200, contamination=0.03, random_state=42))
iso.fit(TR[TR.y == "Normal"][AF])
an = iso.predict(TE[AF]) == -1
harm = (TE.y == "Contamination").values
tp = int((an & harm).sum()); fp = int((an & ~harm).sum()); fn = int((~an & harm).sum()); tn = int((~an & ~harm).sum())
R["iso"] = dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=round(tp / max(tp + fp, 1), 3), recall=round(tp / max(tp + fn, 1), 3),
                flagged_natural=int((an & (TE.y == "Natural change").values).sum()),
                natural_total=int((TE.y == "Natural change").sum()))
joblib.dump(iso, "models/isolation_forest.joblib")

# ------------------------------------------------------------ Assignment 6: confidence + early warning
proba = rf.predict_proba(TE[FEAT]); conf = proba.max(axis=1)
pred_rf = rf.classes_[proba.argmax(axis=1)]
correct = pred_rf == TE.y.values
R["confidence"] = dict(mean=round(float(conf.mean() * 100), 2), correct_mean=round(float(conf[correct].mean() * 100), 2),
                       wrong_mean=round(float(conf[~correct].mean() * 100), 2) if (~correct).any() else None,
                       share_above_90=round(float((conf > 0.9).mean() * 100), 1))
fig, ax = plt.subplots(figsize=(7.5, 3.2))
ax.hist(conf[correct] * 100, bins=30, alpha=0.75, label="Correct predictions", color="#5cb85c")
ax.hist(conf[~correct] * 100, bins=30, alpha=0.75, label="Wrong predictions", color="#d9534f")
ax.set_xlabel("Random Forest confidence (%)"); ax.set_ylabel("Windows"); ax.set_yscale("log"); ax.legend()
ax.set_title("Prediction confidence on the test set"); fig.tight_layout(); fig.savefig("figs/a6_confidence.png"); plt.close()

# detection delay for contamination events in the test set
delays, missed = [], 0
TEs = TE.assign(pred=pred_rf)
for s, g in TEs.groupby("source"):
    g = g.sort_values("ts"); ev = (g.y == "Contamination").astype(int)
    starts = g.index[(ev.diff() == 1).values]
    for st in starts:
        seg = g.loc[st:].iloc[:36]
        seg = seg[seg.y == "Contamination"]
        hit = seg[seg.pred == "Contamination"]
        if len(hit): delays.append((hit.ts.iloc[0] - seg.ts.iloc[0]).total_seconds() / 60)
        else: missed += 1
R["detection"] = dict(events=len(delays) + missed, detected=len(delays), missed=missed,
                      mean_delay_min=round(float(np.mean(delays)), 1) if delays else None,
                      max_delay_min=round(float(np.max(delays)), 1) if delays else None)

# example timeline plot of one contamination event in test set
g = TEs[TEs.source == TEs[TEs.y == "Contamination"].source.iloc[0]].sort_values("ts")
i0 = np.where(g.y.values == "Contamination")[0][0]
w = g.iloc[max(i0 - 36, 0): i0 + 60]
R["event_src"] = str(w.source.iloc[0]); R["event_first_pred_min"] = float((w[w.pred == "Contamination"].ts.min() - w[w.y == "Contamination"].ts.min()).total_seconds() / 60)
fig, ax = plt.subplots(figsize=(9, 3.4))
ax.plot(w.ts, w.wqi, color="#1f5fa8", label="WQI (measured)")
ax.axhline(50, color="red", ls="--", lw=1)
ev = w[w.y == "Contamination"]; ax.axvspan(ev.ts.min(), ev.ts.max(), color="#d9534f", alpha=0.12, label="True contamination")
pc = w[w.pred == "Contamination"]; ax.scatter(pc.ts, pc.wqi, color="#d9534f", s=12, zorder=3, label="Predicted contamination")
ax.set_title(f"Real-time classification of a contamination event – {NICE[w.source.iloc[0]]}"); ax.legend(fontsize=8)
fig.autofmt_xdate(); fig.tight_layout(); fig.savefig("figs/a6_event.png"); plt.close()

# ------------------------------------------------------------ sensor health (1-min level)
def health_feats(g):
    g = g.sort_values("epoch").copy()
    out = pd.DataFrame(index=g.index)
    out["nan"] = g[PARAMS].isna().any(axis=1).astype(int)
    for p in ["ph", "tds", "turb"]:
        x = g[p].ffill()
        med = x.rolling(11, center=True, min_periods=3).median()
        out[f"spk_{p}"] = (x - med).abs() / (med.abs() + 1)
        out[f"flat_{p}"] = x.rolling(30, min_periods=10).std().fillna(0)
        out[f"drift_{p}"] = x.rolling(720, min_periods=60).median() - x.rolling(4320, min_periods=360).median()
    out["fault"] = g["fault"]; out["source"] = g["source"]
    return out


H = pd.concat([health_feats(g) for _, g in raw.groupby("source")]).dropna()
HF = [c for c in H.columns if c not in ("fault", "source")]
htr, hte = [], []
for s, g in H.groupby("source"):
    n = len(g); htr.append(g.iloc[: int(0.7 * n)]); hte.append(g.iloc[int(0.7 * n):])
HTR, HTE = pd.concat(htr), pd.concat(hte)
hrf = RandomForestClassifier(n_estimators=150, min_samples_leaf=5, class_weight="balanced", n_jobs=-1, random_state=42)
hrf.fit(HTR[HF], HTR.fault); hp = hrf.predict(HTE[HF])
# hybrid: deterministic rules first (dropout, flatline), model for the rest
flat = (HTE[["flat_ph", "flat_tds", "flat_turb"]] < 1e-4).any(axis=1).values
hp = np.where(HTE["nan"].values == 1, "dropout", np.where(flat, "flatline", hp))
FL = ["none", "spike", "flatline", "dropout", "ph_drift", "fouling"]
FL = [f for f in FL if f in set(HTE.fault) | set(HTR.fault)]
R["health"] = classification_report(HTE.fault, hp, labels=FL, output_dict=True, zero_division=0)
cm = confusion_matrix(HTE.fault, hp, labels=FL)
fig, ax = plt.subplots(figsize=(5.8, 4.5))
sns.heatmap(cm, annot=True, fmt="d", cmap="Purples", xticklabels=FL, yticklabels=FL, ax=ax, cbar=False)
ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title("Sensor-health model – confusion matrix")
fig.tight_layout(); fig.savefig("figs/a6_health_cm.png"); plt.close()
joblib.dump(hrf, "models/sensor_health_rf.joblib")

# ------------------------------------------------------------ Assignment 7: Arduino decision tree
EF = ["rel_ph", "rel_tds", "rel_turb", "d_tds", "d_turb", "d_ph"]
ymap = {"Normal": 0, "Natural change": 1, "Contamination": 2}
ytr = TR.y.map(ymap); yte = TE.y.map(ymap)
edt = DecisionTreeClassifier(max_depth=5, random_state=42).fit(TR[EF], ytr)
ep = edt.predict(TE[EF])
pr, rc, f1, _ = precision_recall_fscore_support(yte, ep, average="macro", zero_division=0)
R["edge_dt"] = dict(accuracy=round(accuracy_score(yte, ep), 3), macro_f1=round(f1, 3),
                    alert_recall=round(float(((ep == 2) & (yte == 2)).sum() / max((yte == 2).sum(), 1)), 3),
                    nodes=int(edt.tree_.node_count), depth=int(edt.get_depth()))
from micromlgen import port
c = port(edt, classname="WaterStateTree", classmap={0: "NORMAL", 1: "NATURAL", 2: "ALERT"})
open("models/WaterStateTree.h", "w").write(c)
R["edge_dt"]["header_kb"] = round(len(c.encode()) / 1024, 1)
cm = confusion_matrix(yte, ep, labels=[0, 1, 2])
fig, ax = plt.subplots(figsize=(4.6, 3.8))
sns.heatmap(cm, annot=True, fmt="d", cmap="Greens", xticklabels=["Normal", "Natural", "Alert"],
            yticklabels=["Normal", "Natural", "Alert"], ax=ax, cbar=False)
ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title("Arduino decision tree (depth 5)")
fig.tight_layout(); fig.savefig("figs/a7_edge_cm.png"); plt.close()

json.dump(R, open("results/results.json", "w"), indent=1, default=str)
print(json.dumps({k: R[k] for k in ["raw_rows", "clean_rows", "n_train", "n_test", "class_all", "model_comparison",
                                    "iso", "confidence", "detection", "edge_dt", "hampel_removed", "raw_missing"]},
                 indent=1, default=str))
for f in FL: print(f, {k: round(v, 2) for k, v in R["health"][f].items()})
